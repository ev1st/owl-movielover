const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const toast = document.querySelector("#toast");
const modalBackdrop = document.querySelector("#modalBackdrop");
const surveyForm = document.querySelector("#surveyForm");
const genreSelect = document.querySelector("#genreSelect");
const atmosphereSelect = document.querySelector("#atmosphereSelect");

let toastTimer;


const mainOwlImage = document.querySelector(".owl-image");
const defaultOwlImage = mainOwlImage ? mainOwlImage.getAttribute("src") : null;
const savedOwlImage = localStorage.getItem("owlColorImage");
if (savedOwlImage && mainOwlImage) {
  mainOwlImage.onerror = () => {
    mainOwlImage.onerror = null;
    mainOwlImage.src = defaultOwlImage || "assets/sova_roz.png";
    localStorage.removeItem("owlColorImage");
  };
  mainOwlImage.src = savedOwlImage;
}
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

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Не удалось подобрать фильмы.");
  }
  return payload;
}

function addMovieCard(movie) {
  const card = document.createElement("article");
  card.className = "movie-result";

  const title = document.createElement("h3");
  title.textContent = `${movie.movie_name}${movie.year ? ` (${movie.year})` : ""}`;
  card.appendChild(title);

  const meta = document.createElement("p");
  meta.className = "movie-meta";
  const genreNames = {
    action: "Боевик", adventure: "Приключения", animation: "Мультфильм",
    comedy: "Комедия", crime: "Криминал", documentary: "Документальный",
    drama: "Драма", family: "Семейный", fantasy: "Фэнтези", history: "Исторический",
    horror: "Ужасы", music: "Музыкальный", mystery: "Детектив", romance: "Мелодрама",
    "sci-fi": "Фантастика", thriller: "Триллер", war: "Военный", western: "Вестерн",
    biography: "Биография", sport: "Спортивный", short: "Короткометражный",
    musical: "Мюзикл", "film-noir": "Нуар"
  };
  const russianGenres = (movie.genres || []).map((genre) => genreNames[genre.toLowerCase()] || genre);
  const ratingText = Number(movie.rating || 0) > 0 ? `IMDb ${Number(movie.rating).toFixed(1)}` : "IMDb не указан";
  meta.textContent = `${ratingText} · ${russianGenres.join(", ") || "Жанр не указан"}`;
  card.appendChild(meta);

  if (movie.description) {
    const description = document.createElement("p");
    description.textContent = movie.description;
    card.appendChild(description);
  }

  const explanation = document.createElement("p");
  explanation.className = "movie-explanation";
  explanation.textContent = movie.explanation;
  card.appendChild(explanation);
  chatMessages.appendChild(card);
}

function showRecommendations(payload) {
  chatMessages.replaceChildren();
  addMessage(`Нашла ${payload.recommendations.length} фильмов, вась:`, "owl");
  for (const movie of payload.recommendations) addMovieCard(movie);
}

async function loadMovieOptions() {
  try {
    const options = await apiRequest("/api/options");
    const genreNames = {
      action: "Боевик", adventure: "Приключения", animation: "Мультфильм",
      comedy: "Комедия", crime: "Криминал", documentary: "Документальный",
      drama: "Драма", family: "Семейный", fantasy: "Фэнтези", history: "Исторический",
      horror: "Ужасы", music: "Музыкальный", mystery: "Детектив", romance: "Мелодрама",
      "sci-fi": "Фантастика", thriller: "Триллер", war: "Военный", western: "Вестерн",
      biography: "Биография", sport: "Спортивный", short: "Короткометражный",
      musical: "Мюзикл", "film-noir": "Нуар"
    };
    for (const genre of options.genres) {
      const option = document.createElement("option");
      option.value = genre;
      option.textContent = genreNames[genre.toLowerCase()] || genre;
      genreSelect.appendChild(option);
    }
    for (const atmosphere of options.atmospheres) {
      const option = document.createElement("option");
      option.value = atmosphere;
      option.textContent = atmosphere;
      atmosphereSelect.appendChild(option);
    }
    document.querySelector("#yearFrom").placeholder = options.year_min || "";
    document.querySelector("#yearTo").placeholder = options.year_max || "";
  } catch (error) {
    showToast(`Не удалось загрузить варианты анкеты: ${error.message}`);
  }
}

async function requestRecommendations(data) {
  try {
    const payload = await apiRequest("/api/recommendations", {
      method: "POST",
      body: JSON.stringify(data),
    });
    showRecommendations(payload);
  } catch (error) {
    addMessage(error.message, "owl");
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) {
    messageInput.focus();
    showToast("Напиши Сове пару слов о своём настроении, вась!");
    return;
  }
  addMessage(text, "user");
  messageInput.value = "";
  const submitButton = chatForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  try {
    await requestRecommendations({ mode: "free_text", message: text });
  } finally {
    submitButton.disabled = false;
  }
  messageInput.focus();
});

surveyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = surveyForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = "Подбираю фильмы…";
  try {
    await requestRecommendations({
    mode: "survey",
    genre: genreSelect.value || null,
    atmosphere: atmosphereSelect.value || null,
    country: null,
    actor: document.querySelector("#actorInput").value.trim() || null,
    year_from: document.querySelector("#yearFrom").value
      ? Number(document.querySelector("#yearFrom").value)
      : null,
    year_to: document.querySelector("#yearTo").value
      ? Number(document.querySelector("#yearTo").value)
      : null,
    min_rating: document.querySelector("#minRating").value
      ? Number(document.querySelector("#minRating").value)
      : null,
    limit: 20,
    });
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Подобрать фильмы";
  }
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.prompt;
    messageInput.focus();
  });
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

loadMovieOptions();
