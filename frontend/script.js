const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const toast = document.querySelector("#toast");
const modalBackdrop = document.querySelector("#modalBackdrop");

let toastTimer;


const savedOwlImage = localStorage.getItem("owlColorImage");
const mainOwlImage = document.querySelector(".owl-image");
if (savedOwlImage && mainOwlImage) mainOwlImage.src = savedOwlImage;
function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function addMessage(text, type) {
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.textContent = text;
  chatMessages.appendChild(message);
  chatMessages.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function owlReply(text) {
  const normalized = text.toLowerCase();
  if (/ужас|страш|хоррор|жутк/.test(normalized)) {
    return "Скоро все будет, васек.";
  }
  if (/смеш|комед|весел|поржать/.test(normalized)) {
    return "обожди, вась.";
  }
  if (/груст|плак|драма|поплакать/.test(normalized)) {
    return "Не грусти, вась, скоро все будет.";
  }
  if (/загад|детектив|триллер|тайн/.test(normalized)) {
    return "Скоро будет, вась.";
  }
  return "Ууу, доработаем и все будет, вась.";
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) {
    messageInput.focus();
    showToast("Напиши Сове пару слов о своём настроении, вась!");
    return;
  }
  addMessage(text, "user");
  messageInput.value = "";
  addMessage(owlReply(text), "owl");
  messageInput.focus();
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.prompt;
    messageInput.focus();
  });
});

document.querySelector("#registerBtn").addEventListener("click", () => {
  modalBackdrop.classList.add("open");
  modalBackdrop.setAttribute("aria-hidden", "false");
});
function closeModal() {
  modalBackdrop.classList.remove("open");
  modalBackdrop.setAttribute("aria-hidden", "true");
}
document.querySelector("#modalClose").addEventListener("click", closeModal);
document.querySelector("#modalOk").addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (event) => {
  if (event.target === modalBackdrop) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    const page = button.dataset.page;
    if (page === "Главная") {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (page === "Образы") {
      window.location.href = "wardrobe.html";
      return;
    }
    showToast(`Раздел «${page}» появится в следующих версиях сайта, вась!`);
  });
});
