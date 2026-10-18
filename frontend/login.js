const form = document.querySelector(".login-form");
const button = form.querySelector("button[type=submit]");
const note = document.createElement("p");
note.style.cssText = "margin:0;font-size:14px;color:#c0392b;display:none";
form.insertBefore(note, button);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.querySelector("#email").value,
        password: form.querySelector("#password").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      note.textContent = typeof payload.detail === "string" ? payload.detail : "Проверь введённые данные.";
      note.style.display = "block";
      return;
    }
    localStorage.setItem("owlUser", payload.username);
    window.location.href = "index.html";
  } catch (error) {
    note.textContent = "Не удалось связаться с сервером. Он запущен?";
    note.style.display = "block";
  } finally {
    button.disabled = false;
  }
});
