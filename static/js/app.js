const API = "/api";

function getToken() {
    return localStorage.getItem("token");
}

function headers() {
    return {
        "Content-Type": "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {})
    };
}

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        ...options,
        headers: { ...headers(), ...(options.headers || {}) }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
}

function showMessage(message, isError = false) {
    const target = document.getElementById("auth-message");
    if (target) {
        target.textContent = message;
        target.className = `small mt-3 ${isError ? "text-danger" : "text-success"}`;
    } else {
        window.alert(message);
    }
}

function logout() {
    localStorage.removeItem("token");
    window.location.href = "/";
}

function resolveImage(item) {
    return item.image_url || "/static/images/default.jpg";
}

function renderListings(items) {
    const grid = document.getElementById("listings-grid");
    if (!grid) return;
    document.getElementById("catalog-count")?.replaceChildren(document.createTextNode(items.length));
    grid.innerHTML = items.map((item) => `
        <article class="listing-card">
            <img src="${escapeHtml(resolveImage(item))}" alt="${escapeHtml(item.title)}" onerror="this.src='/static/images/default.jpg'">
            <div class="listing-body">
                <span class="badge-soft">${escapeHtml(item.category_name)}</span>
                <h3>${escapeHtml(item.title)}</h3>
                <p>${escapeHtml(item.description || "")}</p>
                <strong>Rs. ${Number(item.price_per_day).toLocaleString()} / day</strong>
                <a class="btn btn-primary w-100 mt-3" href="/item/${item.id}">View details</a>
            </div>
        </article>
    `).join("");
}

async function loadListings(categoryId = "", search = "") {
    const params = new URLSearchParams();
    if (categoryId) params.set("category_id", categoryId);
    if (search) params.set("search", search);
    try {
        renderListings(await apiRequest(`/listings?${params}`));
    } catch (error) {
        showMessage(error.message, true);
    }
}

function handleSearch() {
    loadListings("", document.getElementById("search-input")?.value.trim() || "");
}

async function loadUser() {
    if (!getToken()) return;
    try {
        const user = await apiRequest("/auth/me");
        document.getElementById("auth-btn-group")?.classList.add("d-none");
        document.getElementById("user-profile-group")?.classList.remove("d-none");
        document.getElementById("nav-user-name")?.replaceChildren(document.createTextNode(user.full_name));
        document.getElementById("prof-name")?.replaceChildren(document.createTextNode(user.full_name));
        document.getElementById("prof-email")?.replaceChildren(document.createTextNode(user.email));
    } catch {
        localStorage.removeItem("token");
    }
}

async function handleLogin(event) {
    event.preventDefault();
    try {
        const data = await apiRequest("/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: document.getElementById("login-email").value,
                password: document.getElementById("login-password").value
            })
        });
        localStorage.setItem("token", data.access_token);
        window.location.href = "/";
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function handleRegister(event) {
    event.preventDefault();
    try {
        const email = document.getElementById("reg-email").value;
        const data = await apiRequest("/auth/register", {
            method: "POST",
            body: JSON.stringify({
                full_name: document.getElementById("reg-name").value,
                email,
                password: document.getElementById("reg-password").value
            })
        });
        window.pendingEmail = data.email || email;
        document.getElementById("register-pane")?.classList.add("d-none");
        document.getElementById("otp-container")?.classList.remove("d-none");
        showMessage(data.message);
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function handleOtp(event) {
    event.preventDefault();
    try {
        const data = await apiRequest("/auth/verify-signup-otp", {
            method: "POST",
            body: JSON.stringify({
                email: window.pendingEmail,
                otp_code: document.getElementById("otp-code").value
            })
        });
        localStorage.setItem("token", data.access_token);
        window.location.href = "/";
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function loadItem() {
    const match = window.location.pathname.match(/^\/item\/(\d+)\/?$/);
    if (!match) return;
    try {
        const item = await apiRequest(`/listings/${match[1]}`);
        const values = {
            "item-title": item.title,
            "item-desc": item.description,
            "item-category": item.category_name,
            "item-location": item.location,
            "item-price": `Rs. ${Number(item.price_per_day).toLocaleString()}`,
            "item-deposit": `Rs. ${Number(item.deposit_amount).toLocaleString()}`
        };
        Object.entries(values).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
        const image = document.getElementById("item-image");
        if (image) image.src = resolveImage(item);
    } catch (error) {
        showMessage(error.message, true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("form-login")?.addEventListener("submit", handleLogin);
    document.getElementById("form-register")?.addEventListener("submit", handleRegister);
    document.getElementById("form-otp")?.addEventListener("submit", handleOtp);
    if (document.getElementById("listings-grid")) loadListings();
    loadUser();
    loadItem();
});
