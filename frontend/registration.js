const form = document.querySelector(".register-form");
const button = form.querySelector(".submit-button");
const note = document.createElement("p");
note.style.cssText = "margin:0;font-size:14px;display:none";
form.insertBefore(note, button);

function showNote(text, ok) {
  note.textContent = text;
  note.style.color = ok ? "#2e7d32" : "#c0392b";
  note.style.display = "block";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = form.querySelector("#password").value;
  if (password !== form.querySelector("#confirm-password").value) {
    showNote("Пароли не совпадают, вась.", false);
    return;
  }
  button.disabled = true;
  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: form.querySelector("#username").value,
        email: form.querySelector("#email").value,
        password,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      showNote(typeof payload.detail === "string" ? payload.detail : "Проверь введённые данные.", false);
      return;
    }
    showNote("Аккаунт создан! Перенаправляю на вход…", true);
    setTimeout(() => { window.location.href = "login.html"; }, 900);
  } catch (error) {
    showNote("Не удалось связаться с сервером. Он запущен?", false);
  } finally {
    button.disabled = false;
  }
});
