// Credit: Ayu Itz(https://github.com/iayushanand)
// Description: Typing effect for the home page

// not gonna use this for now

const text1 = "Hi, I am";
const text2 = " farrr"
const speed = 50;


function typewriterEffect(text, elementid) {
    let i = 0;
    const typewriter = setInterval(function() {
      document.getElementById(elementid).textContent += text.charAt(i);
      i++;
      if (i > text.length) {
        clearInterval(typewriter);
      }
    }, speed);
  }
setTimeout(typewriterEffect(text1, "typerwriter-text1"), 0)

setTimeout(typewriterEffect(text2, "typerwriter-text2"), 0)



const cursor = document.getElementById("typewriter-loop")

const texts = ["a back-end developer", "a student", "a game developer", "an engineering aspirant"]

const timeout = ms => new Promise(r => setTimeout(r, ms));


(async () => {
     await timeout(1000)
     document.getElementById("iam").className = ""
     while (true) {
          for (const text of texts) {
               for (const chr of text) {
                    await timeout(50);
                    cursor.textContent += chr;
               }
               await timeout(1000);

               let i = 0;
               for (const _chr of text) {
                    await timeout(25);
                    cursor.textContent = cursor.textContent.substring(0, text.length - ++i);
               }
          }
     }
})();