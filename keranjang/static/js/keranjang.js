
document.addEventListener("DOMContentLoaded", () => {

    /* ========================================
       KONFIRMASI HAPUS BARANG
    ======================================== */

    const dialog = document.getElementById("delete-dialog");
    const description = document.getElementById("delete-description");
    const cancelButton = document.querySelector("[data-cancel-delete]");
    const confirmButton = document.querySelector("[data-confirm-delete]");

    if (dialog && description && cancelButton && confirmButton) {
        let selectedForm = null;
        let previousButton = null;

        // Membuka dialog konfirmasi.
        document.querySelectorAll("[data-open-delete]").forEach((button) => {
            button.addEventListener("click", () => {
                const form = button.closest(".delete-form");

                if (!form) return;

                selectedForm = form;
                previousButton = button;

                const title = form.dataset.itemTitle || "barang ini";

                description.textContent =
                    `Apakah kamu yakin ingin menghapus "${title}" dari keranjang?`;

                dialog.showModal();
            });
        });

        // Membatalkan penghapusan.
        cancelButton.addEventListener("click", () => {
            dialog.close();
        });

        // Melanjutkan penghapusan.
        confirmButton.addEventListener("click", () => {
            if (selectedForm) {
                selectedForm.requestSubmit();
            }
        });

        // Menutup dialog jika backdrop diklik.
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) {
                dialog.close();
            }
        });

        // Mengembalikan fokus setelah dialog ditutup.
        dialog.addEventListener("close", () => {
            selectedForm = null;

            if (previousButton && previousButton.isConnected) {
                previousButton.focus();
            }

            previousButton = null;
        });
    }

    /* ========================================
       FAVORIT MENGGUNAKAN AJAX
    ======================================== */

    const favoriteMessage = document.getElementById("favorite-message");

    document.querySelectorAll(".favorite-form").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            const button = form.querySelector(".favorite-button");
            const favoriteInput = form.querySelector(
                'input[name="is_favorite"]'
            );

            if (!button || !favoriteInput || button.disabled) {
                return;
            }

            button.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    credentials: "same-origin"
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.message || "Gagal memperbarui favorit."
                    );
                }

                const isFavorite = data.is_favorite;

                // Memperbarui tampilan tombol.
                button.classList.toggle("is-favorite", isFavorite);

                button.setAttribute(
                    "aria-pressed",
                    String(isFavorite)
                );

                button.setAttribute(
                    "aria-label",
                    isFavorite
                        ? "Hapus dari favorit"
                        : "Tambahkan ke favorit"
                );

                button.textContent = isFavorite
                    ? "♥ Favorit"
                    : "♡ Tambah Favorit";

                // Menyiapkan nilai untuk klik berikutnya.
                favoriteInput.value = isFavorite ? "false" : "true";

                // Memperbarui pesan.
                if (favoriteMessage) {
                    favoriteMessage.textContent = data.message;
                }

                // Memperbarui posisi kartu favorit.
                const card = form.closest(".cart-card");
                const grid = card?.parentElement;

                if (card && grid) {
                    const cards = Array.from(
                        grid.querySelectorAll(".cart-card")
                    );

                    cards.sort((a, b) => {
                        const aFavorite = a.querySelector(
                            ".favorite-button"
                        )?.classList.contains("is-favorite") || false;

                        const bFavorite = b.querySelector(
                            ".favorite-button"
                        )?.classList.contains("is-favorite") || false;

                        return Number(bFavorite) - Number(aFavorite);
                    });

                    cards.forEach((item) => grid.appendChild(item));
                }

            } catch (error) {
                if (favoriteMessage) {
                    favoriteMessage.textContent =
                        error.message || "Terjadi kesalahan.";
                }

            } finally {
                button.disabled = false;
            }
        });
    });
});
