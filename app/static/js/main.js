function showToast(message, type) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "toast toast-" + (type || "info");
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function () {
    toast.remove();
  }, 3600);
}

function setButtonLoading(btn, isLoading) {
  if (!btn) return;
  if (isLoading) {
    btn.dataset.originalText = btn.textContent;
    btn.textContent = "";
    btn.classList.add("btn-loading");
    btn.disabled = true;
  } else {
    btn.classList.remove("btn-loading");
    btn.disabled = false;
    if (btn.dataset.originalText) {
      btn.textContent = btn.dataset.originalText;
    }
  }
}

document.addEventListener("DOMContentLoaded", function () {
  // Copy campaign link
  const copyBtn = document.getElementById("copy-link-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      const link = copyBtn.getAttribute("data-link");
      if (!navigator.clipboard) {
        showToast("Clipboard not supported in this browser. Please copy the link manually.", "error");
        return;
      }
      navigator.clipboard.writeText(link).then(function () {
        const original = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        showToast("Campaign link copied to clipboard.", "success");
        setTimeout(function () { copyBtn.textContent = original; }, 1500);
      }).catch(function () {
        showToast("Could not copy the link. Please copy it manually.", "error");
      });
    });
  }

  // Simulated payment confirmation buttons
  document.querySelectorAll(".simulate-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const url = btn.getAttribute("data-confirm-url");
      const outcome = btn.getAttribute("data-outcome");
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

      const allSimButtons = document.querySelectorAll(".simulate-btn");
      allSimButtons.forEach(function (b) { setButtonLoading(b, true); });
      setButtonLoading(btn, true); // ensure the clicked one shows spinner even if same node

      fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
        body: "simulated_result=" + encodeURIComponent(outcome)
      })
        .then(function (res) {
          if (!res.ok) {
            throw new Error("Server returned status " + res.status);
          }
          return res.json();
        })
        .then(function (data) {
          const statusEl = document.getElementById("payment-status");
          const statusBox = document.getElementById("status-box");
          if (statusEl) statusEl.textContent = data.status;
          if (statusBox) statusBox.className = "status-box status-" + data.status;

          const controls = document.getElementById("simulate-controls");
          if (controls) controls.style.display = "none";

          if (data.status === "successful") {
            showToast("Payment confirmed successfully.", "success");
            const progressInfo = document.getElementById("progress-info");
            const totalPaidEl = document.getElementById("total-paid");
            const remainingEl = document.getElementById("remaining-amount");
            if (progressInfo && totalPaidEl && data.total_paid !== undefined) {
              totalPaidEl.textContent = Number(data.total_paid).toFixed(2);
              if (remainingEl && data.remaining !== null && data.remaining !== undefined) {
                remainingEl.textContent = Number(data.remaining).toFixed(2);
              }
              progressInfo.style.display = "block";
            }
          } else if (data.status === "failed") {
            showToast("Payment failed. Please try again.", "error");
          } else if (data.status === "cancelled") {
            showToast("Payment cancelled — this campaign is no longer active.", "error");
          }
        })
        .catch(function (err) {
          showToast("Something went wrong confirming the payment. Please try again.", "error");
          allSimButtons.forEach(function (b) { setButtonLoading(b, false); });
        });
    });
  });

  // Generic loading state for normal form submit buttons (close/reopen campaign, etc.)
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      const submitBtn = form.querySelector("button[type=submit], input[type=submit]");
      if (submitBtn && !submitBtn.classList.contains("no-loading-state")) {
        setButtonLoading(submitBtn, true);
      }
    });
  });
});

// Surface unexpected client-side errors instead of failing silently
window.addEventListener("error", function () {
  showToast("Something went wrong on this page. Please refresh and try again.", "error");
});