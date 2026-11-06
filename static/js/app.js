const API = "/api";

function getToken() {
    const token = localStorage.getItem("token");
    return token && token !== "undefined" && token !== "null" ? token : null;
}

function getAuthHeaders() {
    return {
        "Content-Type": "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {})
    };
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
}

function showToast(title, message, isError = false) {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container position-fixed bottom-0 end-0 p-3";
        container.style.zIndex = "9999";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-white ${isError ? "bg-danger" : "bg-success"} border-0`;
    toast.setAttribute("role", "status");
    toast.innerHTML = `<div class="d-flex"><div class="toast-body"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
    container.appendChild(toast);
    if (window.bootstrap?.Toast) {
        const instance = new bootstrap.Toast(toast, { delay: 4500 });
        toast.addEventListener("hidden.bs.toast", () => toast.remove(), { once: true });
        instance.show();
    } else {
        toast.classList.add("show");
        window.setTimeout(() => toast.remove(), 4500);
    }
}

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        ...options,
        headers: { ...getAuthHeaders(), ...(options.headers || {}) }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        if (response.status === 401) localStorage.removeItem("token");
        throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
}

function formatMoney(value) {
    return `Rs. ${Number(value || 0).toLocaleString()}`;
}

function logout() {
    localStorage.removeItem("token");
    window.location.href = "/";
}

async function handleLogin(event) {
    event?.preventDefault();
    const email = document.getElementById("login-email")?.value.trim();
    const password = document.getElementById("login-password")?.value;
    if (!email || !password) return showToast("Missing details", "Enter your email and password.", true);
    try {
        const data = await apiRequest("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password })
        });
        if (data.requires_signup_otp || data.requires_2fa) {
            showOtpStep(data.email || email, data.requires_2fa ? "/auth/verify-2fa-otp" : "/auth/verify-signup-otp", data.message);
            return;
        } else if (data.access_token) {
            localStorage.setItem("token", data.access_token);
        } else {
            throw new Error("Login did not return an access token.");
        }
        window.location.href = "/";
    } catch (error) {
        showToast("Sign in failed", error.message, true);
    }
}

async function handleRegister(event) {
    event?.preventDefault();
    const full_name = document.getElementById("reg-name")?.value.trim();
    const email = document.getElementById("reg-email")?.value.trim();
    const password = document.getElementById("reg-password")?.value;
    if (!full_name || !email || !password) return showToast("Missing details", "Complete all required fields.", true);
    try {
        const data = await apiRequest("/auth/register", {
            method: "POST",
            body: JSON.stringify({ full_name, email, password })
        });
        if (data.access_token) {
            localStorage.setItem("token", data.access_token);
            window.location.href = "/";
            return;
        }
        showOtpStep(data.email || email, "/auth/verify-signup-otp", data.message);
    } catch (error) {
        showToast("Registration failed", error.message, true);
    }
}

function showOtpStep(email, endpoint, message) {
    window.pendingOtpVerification = { email, endpoint };
    document.getElementById("authTabs")?.classList.add("d-none");
    document.getElementById("login-pane")?.classList.add("d-none");
    document.getElementById("register-pane")?.classList.add("d-none");
    document.getElementById("forgot-container")?.classList.add("d-none");
    document.getElementById("otp-container")?.classList.remove("d-none");
    const note = document.getElementById("otp-message");
    if (note) note.textContent = `${message || "Enter the verification code."} Account: ${email}`;
    document.getElementById("otp-code")?.focus();
}

function returnToAuth() {
    window.pendingOtpVerification = null;
    document.getElementById("otp-container")?.classList.add("d-none");
    document.getElementById("forgot-container")?.classList.add("d-none");
    document.getElementById("form-reset-password")?.classList.add("d-none");
    document.getElementById("form-forgot-request")?.classList.remove("d-none");
    document.getElementById("authTabs")?.classList.remove("d-none");
    document.getElementById("login-pane")?.classList.remove("d-none");
    document.getElementById("register-pane")?.classList.remove("d-none");
    if (window.bootstrap?.Tab) {
        bootstrap.Tab.getOrCreateInstance(document.getElementById("login-tab")).show();
    }
}

async function handleOtpSubmit(event) {
    event?.preventDefault();
    const pending = window.pendingOtpVerification;
    const otp_code = document.getElementById("otp-code")?.value.trim();
    if (!pending || !otp_code) return showToast("Enter your code", "Enter the 6-digit code to continue.", true);
    try {
        const data = await apiRequest(pending.endpoint, {
            method: "POST",
            body: JSON.stringify({ email: pending.email, otp_code })
        });
        if (!data.access_token) throw new Error("Verification did not return an access token.");
        localStorage.setItem("token", data.access_token);
        window.location.href = "/";
    } catch (error) {
        showToast("Verification failed", error.message, true);
    }
}

async function handleForgotPasswordRequest(event) {
    event?.preventDefault();
    const email = document.getElementById("forgot-email")?.value.trim();
    if (!email) return showToast("Missing email", "Enter the email address for your account.", true);
    try {
        const data = await apiRequest("/auth/forgot-password", {
            method: "POST",
            body: JSON.stringify({ email })
        });
        window.pendingResetEmail = email;
        const requestForm = document.getElementById("form-forgot-request");
        requestForm?.classList.add("d-none");
        document.getElementById("form-reset-password")?.classList.remove("d-none");
        const note = document.getElementById("forgot-message");
        if (note) note.textContent = `${data.message} Enter the 6-digit code and choose a new password.`;
    } catch (error) {
        showToast("Password reset failed", error.message, true);
    }
}

async function handleResetPasswordSubmit(event) {
    event?.preventDefault();
    const otp_code = document.getElementById("reset-otp-code")?.value.trim();
    const new_password = document.getElementById("reset-new-password")?.value;
    const email = window.pendingResetEmail || document.getElementById("forgot-email")?.value.trim();
    if (!email || !otp_code || !new_password) return showToast("Missing details", "Enter the recovery code and a new password.", true);
    try {
        const data = await apiRequest("/auth/reset-password", {
            method: "POST",
            body: JSON.stringify({ email, otp_code: otp_code.trim(), new_password })
        });
        showToast("Password updated", data.message || "You can now sign in.");
        returnToAuth();
    } catch (error) {
        showToast("Password reset failed", error.message, true);
    }
}

function resolveItemImage(item) {
    if (item.image_url) return item.image_url;
    const category = String(item.category_name || "").toLowerCase();
    if (category.includes("car")) return "/static/images/cars/Toyota_Grande_2025.jpg";
    if (category.includes("electronic")) return "/static/images/electronics/ps5.jpeg";
    if (category.includes("furniture")) return "/static/images/furniture/sofa.jpeg";
    if (category.includes("event")) return "/static/images/furniture/lights.jpeg";
    return "/static/images/default.jpg";
}

async function loadListings(categoryId = "", searchText = "") {
    const grid = document.getElementById("listings-grid");
    if (!grid) return;
    const category = String(categoryId || "");
    const query = String(searchText || "").trim();
    document.querySelectorAll(".category-chip").forEach((button) => {
        const label = button.textContent.trim();
        const selected = !category ? label === "All" :
            label === ({ "1": "Furniture", "2": "Electronics", "3": "Cars", "4": "Events", "5": "Stays" }[category]);
        button.classList.toggle("active", selected);
    });
    grid.innerHTML = `<div class="listing-empty"><div class="spinner-border text-primary" role="status"></div><p>Loading real listings…</p></div>`;
    try {
        const params = new URLSearchParams();
        if (category) params.set("category_id", category);
        if (query) params.set("search", query);
        const data = await apiRequest(`/listings?${params.toString()}`, { headers: {} });
        if (!Array.isArray(data)) throw new Error("The listings API returned an invalid response.");
        const count = document.getElementById("catalog-count");
        if (count) count.textContent = data.length.toLocaleString();
        const inventory = document.getElementById("inventory-count");
        if (inventory) inventory.textContent = `${data.length.toLocaleString()} shown`;
        if (!data.length) {
            grid.innerHTML = `<div class="listing-empty"><i class="bi bi-search"></i><h3>No rentals found</h3><p>Try another category or search term.</p></div>`;
            return;
        }
        grid.innerHTML = data.map((item) => {
            const id = Number(item.id);
            const detailUrl = `/item/${id}`;
            const title = escapeHtml(item.title);
            const image = escapeHtml(resolveItemImage(item));
            const categoryName = escapeHtml(item.category_name || "Marketplace");
            const description = escapeHtml(item.description || "");
            return `<article class="listing-card">
                <div class="listing-card-image">
                    <span class="listing-label">${categoryName}</span>
                    <a href="${detailUrl}" aria-label="View ${title}"><img src="${image}" alt="${title}" onerror="this.src='/static/images/default.jpg'"></a>
                </div>
                <div class="listing-body">
                    <div class="listing-meta"><span class="badge-soft">${categoryName}</span><span class="deposit-text">Deposit: ${formatMoney(item.deposit_amount)}</span></div>
                    <h3 class="listing-title"><a href="${detailUrl}">${title}</a></h3>
                    <p class="listing-description">${description.slice(0, 100)}${description.length > 100 ? "…" : ""}</p>
                    <div class="listing-footer"><div class="price-wrap"><span>${formatMoney(item.price_per_day)}</span><small>/day</small></div>
                        <div class="d-flex gap-2"><button class="quick-button" type="button" onclick="openQuickView(${id})">Quick view</button><a class="quick-button" href="${detailUrl}">Book</a></div>
                    </div>
                </div>
            </article>`;
        }).join("");
    } catch (error) {
        console.error("Listing load failed:", error);
        grid.innerHTML = `<div class="listing-empty"><i class="bi bi-exclamation-circle"></i><h3>Marketplace unavailable</h3><p>${escapeHtml(error.message)}</p><button class="btn btn-primary" type="button" onclick="loadListings('${escapeHtml(category)}','${escapeHtml(query)}')">Retry</button></div>`;
    }
}

function handleSearch() {
    loadListings("", document.getElementById("search-input")?.value || "");
    document.getElementById("listings-grid")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function openQuickView(itemId) {
    try {
        const item = await apiRequest(`/listings/${Number(itemId)}`);
        const set = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };
        set("qv-title", item.title);
        set("qv-category", item.category_name);
        set("qv-desc", item.description);
        set("qv-price", `${formatMoney(item.price_per_day)}/day`);
        set("qv-deposit", formatMoney(item.deposit_amount));
        const image = document.getElementById("qv-image");
        if (image) image.src = resolveItemImage(item);
        window.qvItemId = Number(item.id);
        const detailsLink = document.getElementById("qv-details-link");
        if (detailsLink) detailsLink.href = `/item/${Number(item.id)}`;
        window.activeBookingRates = {
            price: Number(item.price_per_day || 0),
            deposit: Number(item.deposit_amount || 0)
        };
        const start = document.getElementById("qv-start");
        const end = document.getElementById("qv-end");
        const today = new Date().toISOString().slice(0, 10);
        if (start) {
            start.min = today;
            start.value = "";
        }
        if (end) {
            end.min = today;
            end.value = "";
        }
        updateBookingEstimate("qv");
        bootstrap.Modal.getOrCreateInstance(document.getElementById("quickViewModal")).show();
    } catch (error) {
        showToast("Listing unavailable", error.message, true);
    }
}

function updateBookingEstimate(prefix) {
    const startInput = document.getElementById(`${prefix}-start`);
    const endInput = document.getElementById(`${prefix}-end`);
    const output = document.getElementById(`${prefix}-estimate`);
    if (!startInput || !endInput || !output || !window.activeBookingRates) return;
    if (startInput.value) endInput.min = startInput.value;
    if (!startInput.value || !endInput.value) {
        output.textContent = "Choose dates to calculate rental cost and refundable deposit.";
        return;
    }
    const start = new Date(`${startInput.value}T00:00:00`);
    const end = new Date(`${endInput.value}T00:00:00`);
    const days = Math.floor((end - start) / 86400000) + 1;
    if (days < 1) {
        output.textContent = "End date must be on or after the start date.";
        return;
    }
    const rent = days * window.activeBookingRates.price;
    const deposit = window.activeBookingRates.deposit;
    output.textContent = `${days} day${days === 1 ? "" : "s"} · Rent ${formatMoney(rent)} · Refundable deposit ${formatMoney(deposit)} · Due now ${formatMoney(rent + deposit)}`;
}

async function submitBooking(listingId, start, end) {
    if (!getToken()) {
        showToast("Sign in required", "Sign in before confirming a booking.", true);
        window.setTimeout(() => { window.location.href = "/login"; }, 800);
        return;
    }
    try {
        const data = await apiRequest("/bookings", {
            method: "POST",
            body: JSON.stringify({ listing_id: Number(listingId), start_date: start, end_date: end })
        });
        showToast("Booking confirmed", data.message || "Your booking has been placed.");
        window.setTimeout(() => { window.location.href = "/profile"; }, 800);
    } catch (error) {
        showToast("Booking failed", error.message, true);
    }
}

function bookFromModal() {
    const start = document.getElementById("qv-start")?.value;
    const end = document.getElementById("qv-end")?.value;
    if (!window.qvItemId || !start || !end) return showToast("Select dates", "Choose the start and end dates.", true);
    return submitBooking(window.qvItemId, start, end);
}

async function loadSingleItem() {
    const match = window.location.pathname.match(/^\/item\/(\d+)\/?$/);
    if (!match) return;
    try {
        const item = await apiRequest(`/listings/${Number(match[1])}`, { headers: {} });
        const set = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };
        const image = document.getElementById("item-image");
        if (image) {
            image.src = resolveItemImage(item);
            image.alt = item.title || "Rental listing";
        }
        set("item-category", item.category_name);
        set("item-title", item.title);
        set("item-desc", item.description || "No description provided.");
        set("item-price", formatMoney(item.price_per_day));
        set("item-deposit", formatMoney(item.deposit_amount));
        set("item-location", item.location || "Location not provided");
        window.currentListingId = Number(item.id);
        window.activeBookingRates = {
            price: Number(item.price_per_day || 0),
            deposit: Number(item.deposit_amount || 0)
        };
        const today = new Date().toISOString().slice(0, 10);
        ["page-booking-start", "page-booking-end"].forEach((id) => {
            const input = document.getElementById(id);
            if (input) input.min = today;
        });
    } catch (error) {
        document.getElementById("item-title")?.replaceChildren(document.createTextNode("Listing unavailable"));
        showToast("Could not load listing", error.message, true);
    }
}

function bookFromPage() {
    const start = document.getElementById("page-booking-start")?.value;
    const end = document.getElementById("page-booking-end")?.value;
    if (!window.currentListingId || !start || !end) return showToast("Select dates", "Choose the start and end dates.", true);
    return submitBooking(window.currentListingId, start, end);
}

async function loadRecommendations() {
    const section = document.getElementById("ai-section");
    const container = document.getElementById("ai-recs-container");
    if (!section || !container || !getToken()) return;
    try {
        const items = await apiRequest("/recommendations");
        if (!Array.isArray(items) || !items.length) return;
        section.classList.remove("d-none");
        container.innerHTML = items.map((item) => `<article class="listing-card">
            <img src="${escapeHtml(resolveItemImage(item))}" alt="${escapeHtml(item.title)}" onerror="this.src='/static/images/default.jpg'">
            <div class="listing-body"><span class="badge-soft">Recommended for you</span><h3>${escapeHtml(item.title)}</h3>
            <p>${formatMoney(item.price_per_day)}/day</p><button type="button" class="quick-button" onclick="openQuickView(${Number(item.id)})">View details</button></div>
        </article>`).join("");
    } catch (error) {
        console.error("Recommendations unavailable:", error);
    }
}

async function topupWallet() {
    const amount = Number(document.getElementById("topup-amount")?.value);
    if (!Number.isFinite(amount) || amount <= 0) return showToast("Invalid amount", "Enter an amount greater than zero.", true);
    try {
        const data = await apiRequest("/wallet/topup", { method: "POST", body: JSON.stringify({ amount }) });
        showToast("Sandbox credits added", data.message || "Wallet updated.");
        window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
        showToast("Top-up failed", error.message, true);
    }
}

async function loadUser() {
    const token = getToken();
    const authGroup = document.getElementById("auth-btn-group");
    const profileGroup = document.getElementById("user-profile-group");
    if (!token) {
        authGroup?.classList.remove("d-none");
        profileGroup?.classList.add("d-none");
        return;
    }
    try {
        const user = await apiRequest("/auth/me");
        document.getElementById("nav-user-name")?.replaceChildren(document.createTextNode(user.full_name || "Account"));
        const wallet = document.getElementById("wallet-balance");
        if (wallet) wallet.textContent = formatMoney(user.wallet_balance);
        authGroup?.classList.add("d-none");
        profileGroup?.classList.remove("d-none");
        document.getElementById("admin-link")?.classList.toggle("d-none", user.role !== "admin");
        loadRecommendations();
    } catch (error) {
        localStorage.removeItem("token");
        authGroup?.classList.remove("d-none");
        profileGroup?.classList.add("d-none");
    }
}

async function loadProfile() {
    if (!getToken()) {
        window.location.href = "/login";
        return;
    }
    try {
        const [user, bookings, transactions] = await Promise.all([
            apiRequest("/auth/me"),
            apiRequest("/bookings/my"),
            apiRequest("/wallet/transactions")
        ]);
        const setText = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };
        setText("prof-name", user.full_name);
        setText("prof-email", user.email);
        setText("prof-role", user.role);
        setText("prof-wallet", formatMoney(user.wallet_balance));
        setText("prof-header-wallet", formatMoney(user.wallet_balance));
        document.getElementById("nav-seller-hub")?.classList.toggle("d-none", !["admin", "seller"].includes(user.role));
        const bookingBody = document.getElementById("bookings-table");
        if (bookingBody) bookingBody.innerHTML = bookings.length ? bookings.map((booking) => `<tr>
            <td><a href="/item/${Number(booking.listing_id)}" class="text-decoration-none"><strong>${escapeHtml(booking.title)}</strong></a></td>
            <td>${escapeHtml(booking.start_date)} – ${escapeHtml(booking.end_date)}</td>
            <td>${formatMoney(booking.total_price)}<small class="d-block text-muted">+ ${formatMoney(booking.deposit_amount)} refundable deposit</small></td>
            <td><span class="badge text-bg-primary">${escapeHtml(booking.status)}</span></td>
        </tr>`).join("") : `<tr><td colspan="4" class="text-center py-4 text-muted">No bookings yet. Browse the marketplace to make your first booking.</td></tr>`;
        const walletBody = document.getElementById("wallet-history-table");
        if (walletBody) walletBody.innerHTML = transactions.length ? transactions.map((transaction) => {
            const amount = Number(transaction.amount || 0);
            return `<tr><td>${escapeHtml(new Date(transaction.created_at).toLocaleDateString())}</td>
                <td>${escapeHtml(transaction.transaction_type)}</td><td>${escapeHtml(transaction.reference_id || "")}</td>
                <td class="${amount >= 0 ? "text-success" : "text-danger"} fw-bold">${amount >= 0 ? "+" : ""}${formatMoney(amount)}</td></tr>`;
        }).join("") : `<tr><td colspan="4" class="text-center py-4 text-muted">Wallet transactions will appear here.</td></tr>`;
        await loadSellerListings();
    } catch (error) {
        showToast("Account data unavailable", error.message, true);
    }
}

async function loadSellerListings() {
    const table = document.getElementById("seller-inventory-table");
    if (!table) return;
    try {
        const allListings = await apiRequest("/listings", { headers: {} });
        table.innerHTML = allListings.length ? allListings.map((item) => `<tr><td>${Number(item.id)}</td><td>${escapeHtml(item.title)}</td>
            <td>${formatMoney(item.price_per_day)}</td><td>${item.is_available ? "Available" : "Unavailable"}</td>
            <td><button class="btn btn-sm btn-outline-danger" type="button" onclick="deleteListing(${Number(item.id)})">Remove</button></td></tr>`).join("")
            : `<tr><td colspan="5" class="text-center text-muted py-4">No marketplace listings yet.</td></tr>`;
    } catch (error) {
        table.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">${escapeHtml(error.message)}</td></tr>`;
    }
}

async function createListing(event) {
    event?.preventDefault();
    const listing = {
        category_id: Number(document.getElementById("add-category")?.value),
        title: document.getElementById("add-title")?.value.trim(),
        description: document.getElementById("add-desc")?.value.trim(),
        price_per_day: Number(document.getElementById("add-price")?.value),
        deposit_amount: Number(document.getElementById("add-deposit")?.value || 0),
        location: document.getElementById("add-location")?.value.trim(),
        image_url: document.getElementById("add-image")?.value.trim() || null
    };
    try {
        const result = await apiRequest("/listings", { method: "POST", body: JSON.stringify(listing) });
        showToast("Listing created", result.message || "Your listing is now in the marketplace.");
        bootstrap.Modal.getOrCreateInstance(document.getElementById("newListingModal")).hide();
        document.getElementById("form-create-listing")?.reset();
        await loadSellerListings();
    } catch (error) {
        showToast("Could not create listing", error.message, true);
    }
}

async function deleteListing(id) {
    if (!window.confirm("Remove this listing from the marketplace?")) return;
    try {
        const result = await apiRequest(`/listings/${Number(id)}`, { method: "DELETE" });
        showToast("Listing removed", result.message || "Listing removed.");
        await loadAdminData();
        await loadSellerListings();
    } catch (error) {
        showToast("Could not remove listing", error.message, true);
    }
}

let currentAdminTxFilter = "ALL";
function filterAdminTx(type, button) {
    currentAdminTxFilter = type;
    button?.parentElement?.querySelectorAll("button").forEach((node) => node.classList.toggle("active", node === button));
    loadAdminTransactions();
}
function handleAdminTxSearch() {
    clearTimeout(window.adminSearchTimeout);
    window.adminSearchTimeout = window.setTimeout(loadAdminTransactions, 250);
}

async function loadAdminData() {
    if (!getToken()) return window.location.assign("/login");
    try {
        const currentUser = await apiRequest("/auth/me");
        if (currentUser.role !== "admin") {
            showToast("Admin access required", "This page is only available to administrators.", true);
            window.setTimeout(() => { window.location.href = "/"; }, 700);
            return;
        }
        const [users, listings, bookings] = await Promise.all([
            apiRequest("/admin/users"), apiRequest("/listings", { headers: {} }), apiRequest("/admin/bookings")
        ]);
        const userTable = document.getElementById("admin-users-table");
        if (userTable) userTable.innerHTML = users.length ? users.map((user) => `<tr>
            <td>${Number(user.id)}</td><td>${escapeHtml(user.full_name)}</td><td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.role)}</td><td>${formatMoney(user.wallet_balance)}</td><td>${user.is_verified ? "Verified" : "Pending"}</td></tr>`).join("")
            : `<tr><td colspan="6" class="text-center text-muted">No registered users.</td></tr>`;
        const listingTable = document.getElementById("admin-listings-table");
        if (listingTable) listingTable.innerHTML = listings.length ? listings.map((item) => `<tr>
            <td>${Number(item.id)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.category_name)}</td>
            <td>${formatMoney(item.price_per_day)}</td><td>${formatMoney(item.deposit_amount)}</td><td>${escapeHtml(item.location || "")}</td>
            <td><button class="btn btn-sm btn-outline-danger" type="button" onclick="deleteListing(${Number(item.id)})">Remove</button></td></tr>`).join("")
            : `<tr><td colspan="7" class="text-center text-muted">No listings.</td></tr>`;
        const bookingsTable = document.getElementById("admin-bookings-table");
        if (bookingsTable) bookingsTable.innerHTML = bookings.length ? bookings.map((booking) => `<tr>
            <td>${Number(booking.id)}</td><td>${escapeHtml(booking.full_name)}<small class="d-block text-muted">${escapeHtml(booking.email)}</small></td>
            <td><a href="/item/${Number(booking.listing_id)}">${escapeHtml(booking.title)}</a></td>
            <td>${escapeHtml(booking.start_date)} – ${escapeHtml(booking.end_date)}</td><td>${formatMoney(booking.total_price)}</td>
            <td>${escapeHtml(booking.status)}</td></tr>`).join("") : `<tr><td colspan="6" class="text-center text-muted">No bookings.</td></tr>`;
        const stat = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; };
        stat("stat-users", users.length);
        stat("stat-listings", listings.length);
        stat("stat-bookings", bookings.length);
        stat("stat-revenue", formatMoney(users.reduce((sum, user) => sum + Number(user.wallet_balance || 0), 0)));
        await loadAdminTransactions();
    } catch (error) {
        showToast("Admin data unavailable", error.message, true);
    }
}

async function loadAdminTransactions() {
    const table = document.getElementById("admin-tx-table");
    if (!table) return;
    const params = new URLSearchParams({ tx_type: currentAdminTxFilter });
    const search = document.getElementById("admin-tx-search")?.value.trim();
    if (search) params.set("search", search);
    try {
        const transactions = await apiRequest(`/admin/transactions?${params}`);
        const stat = document.getElementById("stat-tx-count");
        if (stat) stat.textContent = transactions.length;
        table.innerHTML = transactions.length ? transactions.map((tx) => `<tr>
            <td>${Number(tx.id)}</td><td>${escapeHtml(tx.full_name)}<br><small>${escapeHtml(tx.email)}</small></td>
            <td>${escapeHtml(tx.transaction_type)}</td><td>${escapeHtml(tx.reference_id || "")}</td>
            <td>${formatMoney(tx.amount)}</td><td>${escapeHtml(tx.created_at)}</td>
            <td><button class="btn btn-sm btn-outline-primary" type="button" onclick="inspectTransaction(${Number(tx.id)})">Inspect</button></td></tr>`).join("")
            : `<tr><td colspan="7" class="text-center text-muted py-4">No transaction records found.</td></tr>`;
    } catch (error) {
        table.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4">${escapeHtml(error.message)}</td></tr>`;
    }
}

async function inspectTransaction(id) {
    try {
        const data = await apiRequest(`/admin/transactions/${Number(id)}`);
        const tx = data.transaction;
        const modalContent = document.getElementById("tx-modal-content");
        if (modalContent) modalContent.innerHTML = `<dl class="row mb-0">
            <dt class="col-sm-4">Transaction</dt><dd class="col-sm-8">#${Number(tx.id)} — ${escapeHtml(tx.transaction_type)}</dd>
            <dt class="col-sm-4">User</dt><dd class="col-sm-8">${escapeHtml(tx.full_name)} (${escapeHtml(tx.email)})</dd>
            <dt class="col-sm-4">Amount</dt><dd class="col-sm-8">${formatMoney(tx.amount)}</dd>
            <dt class="col-sm-4">Reference</dt><dd class="col-sm-8">${escapeHtml(tx.reference_id)}</dd>
            ${data.booking_info ? `<dt class="col-sm-4">Booking</dt><dd class="col-sm-8">${escapeHtml(data.booking_info.listing_title || "")}</dd>` : ""}</dl>`;
        const refund = document.getElementById("btn-modal-refund");
        if (refund) {
            refund.classList.toggle("d-none", Number(tx.amount) >= 0 || tx.transaction_type === "REFUND");
            refund.onclick = () => issueRefund(Number(tx.id));
        }
        bootstrap.Modal.getOrCreateInstance(document.getElementById("txDetailModal")).show();
    } catch (error) {
        showToast("Could not inspect transaction", error.message, true);
    }
}

async function issueRefund(id) {
    if (!window.confirm("Refund this booking payment to the user's Rentify Credits wallet?")) return;
    try {
        const result = await apiRequest(`/admin/transactions/${Number(id)}/refund`, { method: "POST" });
        showToast("Refund issued", result.message);
        bootstrap.Modal.getInstance(document.getElementById("txDetailModal"))?.hide();
        await loadAdminData();
    } catch (error) {
        showToast("Refund failed", error.message, true);
    }
}

async function loadSettings2FA() {
    if (!getToken()) {
        window.location.href = "/login";
        return;
    }
    try {
        const user = await apiRequest("/auth/me");
        const toggle = document.getElementById("2fa-toggle-switch");
        if (toggle) toggle.checked = Boolean(user.two_factor_enabled);
        const status = document.getElementById("2fa-status-text");
        if (status) status.textContent = `Status: ${user.two_factor_enabled ? "Enabled" : "Disabled"}`;
    } catch (error) {
        showToast("Settings unavailable", error.message, true);
    }
}

async function handle2FAToggle(toggle) {
    try {
        const result = await apiRequest("/auth/toggle-2fa", {
            method: "POST", body: JSON.stringify({ enabled: toggle.checked })
        });
        showToast("Security settings updated", result.message);
        loadSettings2FA();
    } catch (error) {
        toggle.checked = !toggle.checked;
        showToast("Could not update 2FA", error.message, true);
    }
}

async function changePassword() {
    const old_password = document.getElementById("old-password")?.value;
    const new_password = document.getElementById("new-password")?.value;
    const confirm = document.getElementById("confirm-password")?.value;
    if (!old_password || !new_password || !confirm) return showToast("Missing details", "Complete all password fields.", true);
    if (new_password !== confirm) return showToast("Passwords do not match", "Confirm the new password correctly.", true);
    try {
        const data = await apiRequest("/auth/change-password", {
            method: "POST", body: JSON.stringify({ old_password, new_password })
        });
        showToast("Password updated", data.message);
        ["old-password", "new-password", "confirm-password"].forEach((id) => {
            const input = document.getElementById(id);
            if (input) input.value = "";
        });
    } catch (error) {
        showToast("Could not update password", error.message, true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("form-login")?.addEventListener("submit", handleLogin);
    document.getElementById("form-register")?.addEventListener("submit", handleRegister);
    document.getElementById("form-otp")?.addEventListener("submit", handleOtpSubmit);
    document.getElementById("form-forgot-request")?.addEventListener("submit", handleForgotPasswordRequest);
    document.getElementById("form-reset-password")?.addEventListener("submit", handleResetPasswordSubmit);
    document.getElementById("form-create-listing")?.addEventListener("submit", createListing);
    if (document.getElementById("listings-grid")) {
        loadListings();
        loadUser();
    }
    if (document.getElementById("bookings-table")) loadProfile();
    if (document.getElementById("admin-tx-table")) loadAdminData();
    if (/^\/item\/\d+\/?$/.test(window.location.pathname)) {
        loadSingleItem();
        loadUser();
    }
    if (document.getElementById("2fa-toggle-switch")) loadSettings2FA();
    ["qv", "page-booking"].forEach((prefix) => {
        [`${prefix}-start`, `${prefix}-end`].forEach((id) => {
            document.getElementById(id)?.addEventListener("change", () => updateBookingEstimate(prefix));
        });
    });
});
