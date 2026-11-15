let cart = {};
let products = initialProducts.map(product => ({
    ...product,
    price: Number(product.price),
    stock: Number(product.stock)
}));

const $ = id => document.getElementById(id);

const currency = amount =>
    "₹" + Number(amount).toFixed(2);

function addProduct(id, quantity = 1) {
    const product = products.find(p => Number(p.id) === Number(id));

    if (!product) {
        alert("Product not found.");
        return;
    }

    if (!Number.isInteger(quantity) || quantity <= 0) {
        alert("Quantity must be a positive whole number.");
        return;
    }

    const currentQuantity = cart[id]?.quantity || 0;

    if (currentQuantity + quantity > product.stock) {
        alert("Not enough stock for " + product.name);
        return;
    }

    if (!cart[id]) {
        cart[id] = {
            id: product.id,
            name: product.name,
            price: product.price,
            quantity: 0
        };
    }

    cart[id].quantity += quantity;

    renderCart();
}

function changeQuantity(id, change) {
    if (!cart[id]) return;

    const product = products.find(p => Number(p.id) === Number(id));
    const newQuantity = cart[id].quantity + change;

    if (newQuantity <= 0) {
        delete cart[id];
    } else if (newQuantity > product.stock) {
        alert("Not enough stock.");
        return;
    } else {
        cart[id].quantity = newQuantity;
    }

    renderCart();
}

function removeProduct(id) {
    delete cart[id];
    renderCart();
}

function clearCart() {
    if (Object.keys(cart).length === 0) return;

    if (confirm("Are you sure you want to clear the cart?")) {
        cart = {};
        renderCart();
        $("receipt").innerHTML = "";
    }
}

function getTotals() {
    const subtotal = Object.values(cart).reduce(
        (sum, item) => sum + item.price * item.quantity,
        0
    );

    const discountPercent = Number($("discount").value);

    const safeDiscountPercent =
        Number.isFinite(discountPercent)
            ? Math.min(100, Math.max(0, discountPercent))
            : 0;

    const discount = subtotal * safeDiscountPercent / 100;
    const tax = (subtotal - discount) * 0.05;
    const total = subtotal - discount + tax;

    return { subtotal, discount, tax, total };
}

function renderCart() {
    const container = $("cartItems");
    container.innerHTML = "";

    const items = Object.values(cart);

    if (items.length === 0) {
        container.innerHTML = "<p>Your cart is empty.</p>";
    }

    items.forEach(item => {
        const row = document.createElement("div");
        row.className = "cart-row";

        const details = document.createElement("div");

        const name = document.createElement("strong");
        name.textContent = item.name;

        const price = document.createElement("small");
        price.textContent = currency(item.price) + " each";

        details.append(name, price);

        const controls = document.createElement("div");
        controls.className = "quantity-controls";

        const minus = document.createElement("button");
        minus.textContent = "−";
        minus.onclick = () => changeQuantity(item.id, -1);

        const quantity = document.createElement("span");
        quantity.textContent = item.quantity;

        const plus = document.createElement("button");
        plus.textContent = "+";
        plus.onclick = () => changeQuantity(item.id, 1);

        controls.append(minus, quantity, plus);

        const remove = document.createElement("button");
        remove.className = "remove-button";
        remove.textContent = "Remove";
        remove.onclick = () => removeProduct(item.id);

        row.append(details, controls, remove);
        container.appendChild(row);
    });

    const totals = getTotals();

    $("subtotal").textContent = currency(totals.subtotal);
    $("discountAmount").textContent = currency(totals.discount);
    $("tax").textContent = currency(totals.tax);
    $("total").textContent = currency(totals.total);
}

$("discount").addEventListener("input", renderCart);

$("search").addEventListener("input", event => {
    const query = event.target.value.toLowerCase();

    document.querySelectorAll(".product-card").forEach(card => {
        card.style.display =
            card.dataset.name.toLowerCase().includes(query)
                ? ""
                : "none";
    });
});

async function checkout() {
    const items = Object.values(cart);

    if (items.length === 0) {
        alert("Please add products to the cart.");
        return;
    }

    if (!confirm("Complete this sale and generate the bill?")) {
        return;
    }

    const button = document.querySelector(".checkout-button");
    button.disabled = true;

    try {
        const response = await fetch("/api/checkout", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                items,
                customer_name: $("customerName").value,
                customer_phone: $("customerPhone").value,
                discount_percent: $("discount").value
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Checkout failed.");
        }

        showReceipt(result);

        alert(
            "Bill generated successfully!\n" +
            "Invoice number: " + result.sale_id +
            "\nTotal: " + currency(result.total)
        );

        cart = {};
        renderCart();

        // Refresh stock and sales dashboard.
        setTimeout(() => location.reload(), 1000);

    } catch (error) {
        alert(error.message);
    } finally {
        button.disabled = false;
    }
}

function showReceipt(result) {
    const receipt = $("receipt");
    receipt.innerHTML = "";

    const heading = document.createElement("h2");
    heading.textContent = "SmartCart AI — Receipt";

    const invoice = document.createElement("p");
    invoice.textContent = "Invoice #" + result.sale_id;

    const customer = document.createElement("p");
    customer.textContent =
        "Customer: " + (result.customer_name || "Walk-in customer");

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");

    const header = document.createElement("tr");

    ["Product", "Qty", "Price", "Amount"].forEach(label => {
        const th = document.createElement("th");
        th.textContent = label;
        header.appendChild(th);
    });

    thead.appendChild(header);

    result.items.forEach(item => {
        const row = document.createElement("tr");

        [
            item.name,
            item.quantity,
            currency(item.price),
            currency(item.line_total)
        ].forEach(value => {
            const td = document.createElement("td");
            td.textContent = value;
            row.appendChild(td);
        });

        tbody.appendChild(row);
    });

    table.append(thead, tbody);

    const totals = document.createElement("div");

    totals.innerHTML = `
        <hr>
        <p>Subtotal: ${currency(result.subtotal)}</p>
        <p>Discount: ${currency(result.discount)}</p>
        <p>Demo tax: ${currency(result.tax)}</p>
        <h3>Total: ${currency(result.total)}</h3>
        <button onclick="window.print()">Print Bill</button>
    `;

    receipt.append(heading, invoice, customer, table, totals);

    // Read out the total if speech synthesis is available.
    if ("speechSynthesis" in window) {
        const speech = new SpeechSynthesisUtterance(
            "Your total bill amount is " + result.total + " rupees."
        );

        window.speechSynthesis.speak(speech);
    }
}

// Voice billing.
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
    const recognition = new SpeechRecognition();

    recognition.lang = "en-IN";
    recognition.continuous = false;
    recognition.interimResults = false;

    $("voiceButton").addEventListener("click", () => {
        $("voiceStatus").textContent = "Listening...";

        try {
            recognition.start();
        } catch (error) {
            $("voiceStatus").textContent =
                "Voice recognition is already running.";
        }
    });

    recognition.onresult = event => {
        const transcript =
            event.results[0][0].transcript.toLowerCase().trim();

        $("voiceStatus").textContent = "You said: " + transcript;

        processVoiceCommand(transcript);
    };

    recognition.onerror = event => {
        $("voiceStatus").textContent =
            "Voice error: " + event.error +
            ". You can use manual billing instead.";
    };

    recognition.onend = () => {
        $("voiceButton").disabled = false;
    };

} else {
    $("voiceButton").disabled = true;
    $("voiceStatus").textContent =
        "Speech recognition is not supported in this browser. " +
        "Use manual billing or try a compatible browser.";
}

function processVoiceCommand(command) {
    if (command.includes("calculate total")) {
        const totals = getTotals();

        $("voiceStatus").textContent =
            "Your current total is " + currency(totals.total);

        if ("speechSynthesis" in window) {
            speechSynthesis.speak(
                new SpeechSynthesisUtterance(
                    "Your total is " + totals.total + " rupees."
                )
            );
        }

        return;
    }

    if (command.includes("clear cart")) {
        clearCart();
        return;
    }

    if (command.includes("generate bill")) {
        checkout();
        return;
    }

    if (command.includes("print bill")) {
        window.print();
        return;
    }

    const quantityMatch = command.match(/\b(\d+)\b/);
    const quantity = quantityMatch ? Number(quantityMatch[1]) : 1;

    const productText = command
        .replace(/\b(add|please|to|cart|of|product)\b/g, " ")
        .replace(/\b\d+\b/g, " ")
        .replace(/\b(kilograms?|kgs?|kg|grams?|g|litres?|liters?|l|packets?|pieces?|pcs?)\b/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    if (!productText) {
        $("voiceStatus").textContent =
            "Please say a product name, such as Add 2 Rice.";
        return;
    }

    const product = products.find(p =>
        p.name.toLowerCase() === productText
    );

    if (!product) {
        $("voiceStatus").textContent =
            "Product not found: " + productText;
        return;
    }

    addProduct(product.id, quantity);
}

// Initial display.
renderCart();