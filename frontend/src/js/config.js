// Backend address: local while testing, Render when deployed
const API_BASE =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://mmust-fees-backend.onrender.com";
