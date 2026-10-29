
document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("delete-dialog");
    const description = document.getElementById("delete-description");
    const cancelButton = document.querySelector("[data-cancel-delete]");
    const confirmButton = document.querySelector("[data-confirm-delete]");

    if (!dialog || !description || !cancelButton || !confirmButton) {
        return;
    }

    let selectedForm = null;
    let previousButton = null;

    // Buka dialog saat ikon hapus ditekan.
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

    // Batal: tutup dialog tanpa menghapus barang.
    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    // Konfirmasi: kirim form POST ke Django.
    confirmButton.addEventListener("click", () => {
        if (selectedForm) {
            selectedForm.requestSubmit();
        }
    });

    // Klik di luar kotak dialog menutup dialog, bukan menghapus barang.
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    // Kembalikan fokus setelah dialog ditutup.
    dialog.addEventListener("close", () => {
        selectedForm = null;

        if (previousButton && previousButton.isConnected) {
            previousButton.focus();
        }

        previousButton = null;
    });
});
