const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const toast = document.querySelector("#toast");
const modalBackdrop = document.querySelector("#modalBackdrop");

let toastTimer;
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
    return "Ууу, вась, выбираем что-то атмосферное! В полноценной версии я уточню, насколько страшно тебе, вась, хочется, и подберу фильмы.";
  }
  if (/смеш|комед|весел|поржать/.test(normalized)) {
    return "Записала: сегодня васе нужен лёгкий и смешной фильм!  В полноценной версии подберу комедии под твой вайб, вась.";
  }
  if (/груст|плак|драма|поплакать/.test(normalized)) {
    return "Поняла настроение, вась. Иногда хорошая драма — именно то, что нужно. Когда подключим рекомендатель, я смогу подобрать варианты по твоим предпочтениям , вась.";
  }
  if (/загад|детектив|триллер|тайн/.test(normalized)) {
    return "О, люблю кинозагадки, вась! Для тебя просится что-то с тайнами и неожиданными поворотами. В рабочей версии я предложу подборку, вась.";
  }
  return "Ууу, я тебя услышала, вась! Это демо внешнего вида: пока я не подключена к Python, поэтому не могу честно выдать настоящие рекомендации, вась.";
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
    showToast(`Раздел «${page}» появится в следующих версиях сайта, вась!`);
  });
});
