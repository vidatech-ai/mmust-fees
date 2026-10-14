// Backend address: local while testing, replace the second URL when you deploy
const API_BASE =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://YOUR-API-URL";
