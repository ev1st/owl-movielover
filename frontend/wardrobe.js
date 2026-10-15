const preview = document.querySelector("#owlPreview");
const options = [...document.querySelectorAll(".color-option")];


function selectColor(button) {
  const imagePath = `assets/${button.dataset.image}`;
  preview.src = imagePath;
  preview.dataset.imagePath = imagePath;
  localStorage.setItem("owlColorImage", imagePath);

  options.forEach(option => {
    const selected = option === button;
    option.classList.toggle("selected", selected);
    option.setAttribute("aria-pressed", String(selected));
  });
}

options.forEach(button => button.addEventListener("click", () => selectColor(button)));
const savedImage = localStorage.getItem("owlColorImage");
const initial = options.find(button => `assets/${button.dataset.image}` === savedImage) || options[0];
selectColor(initial);
