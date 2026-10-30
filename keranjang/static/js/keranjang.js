
document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("delete-dialog");
    const description = document.getElementById("delete-description");
    const cancelButton = document.querySelector("[data-cancel-delete]");
    const confirmButton = document.querySelector("[data-confirm-delete]");

    // Hentikan jika elemen dialog tidak tersedia di halaman.
    if (!dialog || !description || !cancelButton || !confirmButton) {
        return;
    }

    let selectedForm = null;
    let previousButton = null;

    // Buka dialog saat ikon hapus diklik.
    document.querySelectorAll("[data-open-delete]").forEach((button) => {
        button.addEventListener("click", () => {
            const form = button.closest(".delete-form");

            if (!form) {
                return;
            }

            selectedForm = form;
            previousButton = button;

            const title = form.dataset.itemTitle || "barang ini";

            description.textContent =
                `Apakah kamu yakin ingin menghapus "${title}" dari keranjang?`;

            dialog.showModal();
        });
    });

    // Tutup dialog tanpa menghapus barang.
    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    // Kirim form POST setelah pengguna mengonfirmasi.
    confirmButton.addEventListener("click", () => {
        if (!selectedForm) {
            return;
        }

        if (typeof selectedForm.requestSubmit === "function") {
            selectedForm.requestSubmit();
        } else {
            selectedForm.submit();
        }
    });

    // Klik backdrop menutup dialog.
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    // Bersihkan pilihan dan kembalikan fokus setelah dialog ditutup.
    dialog.addEventListener("close", () => {
        selectedForm = null;

        if (previousButton && previousButton.isConnected) {
            previousButton.focus();
        }

        previousButton = null;
    });
});
