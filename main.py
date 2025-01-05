import os
import json
import fastapi
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, Request, Form, UploadFile, File
from pydantic import BaseModel
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Load environment variables
load_dotenv()

# Firebase configuration using environment variable
firebase_config = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))
firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")

cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)

db = firestore.client()

app = fastapi.FastAPI(title="farrr")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class GoogleAuth(BaseModel):
    id_token: str

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dm")
async def dm(request: Request):
    return templates.TemplateResponse("dm.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup")
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/additional-info")
async def additional_info(request: Request):
    return templates.TemplateResponse("additional_info.html", {"request": request})

@app.post("/verify-token")
async def verify_token(google_auth: GoogleAuth):
    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(google_auth.id_token)
        uid = decoded_token['uid']
        
        # Check if the user is new
        user_record = auth.get_user(uid)
        if not user_record.display_name:
            return {"message": "New user", "uid": uid, "redirect": "/additional-info"}
        
        return {"message": "Token is valid", "uid": uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/submit-additional-info")
async def submit_additional_info(request: Request, uid: str = Form(...), username: str = Form(...), name: str = Form(...)):
    try:
        # Ensure username is unique and case-insensitive
        username_lower = username.lower()
        users_ref = db.collection('users').where('username_lower', '==', username_lower).get()
        if users_ref:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Update the user record with additional information
        update_data = {
            "display_name": name
        }
        
        auth.update_user(uid, **update_data)
        
        # Save the username to Firestore
        user_ref = db.collection('users').document(uid)
        user_ref.set({
            'username': username,
            'username_lower': username_lower,
            'name': name,
            'email': auth.get_user(uid).email
        })
        
        return {"message": "User information updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/settings")
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.post("/update-settings")
async def update_settings(request: Request, uid: str = Form(...), username: str = Form(None), name: str = Form(None)):
    try:
        # Update the user record with new information
        update_data = {
            "display_name": name
        }
        
        auth.update_user(uid, **update_data)
    
        # Update the username in Firestore
        user_ref = db.collection('users').document(uid)
        ud = {}
        if username:
            check = db.collection('users').where('username_lower', '==', username.lower()).get()
            if check:
                raise HTTPException(status_code=400, detail="Username already taken")
            ud['username'] = username
        if name:
            ud['name'] = name
        if ud:
            user_ref.update(ud)
        
        return {"message": "Settings updated successfully", "redirect": "/"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/profile/{username}")
async def profile(request: Request, username: str):
    user_ref = db.collection('users').where('username', '==', username).get()
    if not user_ref:
        raise HTTPException(status_code=404, detail="User not found")
    ur = user_ref[0]
    user_data = ur.to_dict()
    user_data['uid'] = ur.id
    return templates.TemplateResponse("profile.html", {"request": request, "user": user_data})

@app.post("/follow")
async def follow(request: Request, uid: str = Form(...), follow_uid: str = Form(...)):
    try:
        user_ref = db.collection('users').document(uid)
        follow_ref = db.collection('users').document(follow_uid)
        
        user_data = user_ref.get().to_dict()
        follow_data = follow_ref.get().to_dict()
        
        if 'following' not in user_data:
            user_data['following'] = []
        if 'followers' not in follow_data:
            follow_data['followers'] = []
        
        if follow_uid not in user_data['following']:
            user_data['following'].append(follow_uid)
            follow_data['followers'].append(uid)
        
        user_ref.update(user_data)
        follow_ref.update(follow_data)
        
        # Create a notification
        notification_ref = db.collection('notifications').document()
        notification_ref.set({
            'type': 'follow',
            'data': uid + ":" + user_data['username'],
            'to_uid': follow_uid,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'read': False
        })
        
        # If user has more than 20 notifications, delete the oldest one
        notifications_ref = db.collection('notifications').where('to_uid', '==', follow_uid).order_by('timestamp', direction=firestore.Query.DESCENDING).get()
        if len(notifications_ref) > 20:
            db.collection('notifications').document(notifications_ref[-1].id).delete()
        
        return {"message": "Followed successfully", "redirect": f"/profile/{follow_data['username']}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/notifications/{uid}")
async def get_notifications(request: Request, uid: str):
    try:
        notifications_ref = db.collection('notifications').where('to_uid', '==', uid).order_by('timestamp', direction=firestore.Query.DESCENDING).get()
        notifications = [notification.to_dict() for notification in notifications_ref]
        for notification in notifications_ref:
            notification.reference.update({'read': True})
        return templates.TemplateResponse("notifications.html", {"request": request, "notifications": notifications})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/unfollow")
async def unfollow(request: Request, uid: str = Form(...), follow_uid: str = Form(...)):
    try:
        user_ref = db.collection('users').document(uid)
        follow_ref = db.collection('users').document(follow_uid)
        
        user_data = user_ref.get().to_dict()
        follow_data = follow_ref.get().to_dict()
        
        if 'following' not in user_data:
            user_data['following'] = []
        if 'followers' not in follow_data:
            follow_data['followers'] = []
        
        if follow_uid in user_data['following']:
            user_data['following'].remove(follow_uid)
            follow_data['followers'].remove(uid)
        
        user_ref.update(user_data)
        follow_ref.update(follow_data)
        
        return {"message": "Unfollowed successfully", "redirect": f"/profile/{follow_data['username']}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/check-follow-status")
async def check_follow_status(uid: str, follow_uid: str):
    try:
        user_ref = db.collection('users').document(uid)
        user_data = user_ref.get().to_dict()
        is_following = follow_uid in user_data.get('following', [])
        return {"isFollowing": is_following}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/search")
async def search(request: Request, query: str):
    users_ref = db.collection('users').where('username', '>=', query).where('username', '<=', query + '\uf8ff').get()
    users = [user.to_dict() for user in users_ref]
    
    if not users:
        users_ref = db.collection('users').where('name', '>=', query).where('name', '<=', query + '\uf8ff').get()
        users = [user.to_dict() for user in users_ref]
    
    return templates.TemplateResponse("search.html", {"request": request, "users": users})