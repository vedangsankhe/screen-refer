// The backend address. Locally it is the FastAPI dev server; after deploying, put your Render URL below.
const local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
export const API_URL = local ? 'http://localhost:8000' : 'https://screen-refer.onrender.com';
