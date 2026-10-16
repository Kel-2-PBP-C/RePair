(() => {
    'use strict';
    const editor = document.querySelector('[data-profile-editor]');
    if (!editor) return;
    const editButton = editor.querySelector('[data-profile-edit]');
    const saveActions = editor.querySelector('[data-profile-save]');
    const extraFields = editor.querySelector('[data-profile-extra]');
    const cancelLink = editor.querySelector('[data-profile-cancel]');
    const summaryInputs = [...editor.querySelectorAll('.settings-profile-fields > .settings-field input:not([type="hidden"])')];
    const categories = [...editor.querySelectorAll('.settings-category input')];
    const locationToggle = editor.querySelector('.brand-location-toggle');
    const locationInput = editor.querySelector('.brand-location-control input');
    const initialValues = [...editor.elements].map((field) => ({ field, value: field.value, checked: field.checked }));
    const hasErrors = editor.dataset.profileInvalid === 'true';
    let editing = hasErrors;
    function setEditing(nextEditing, focus = false) {
        editing = nextEditing;
        editor.classList.toggle('settings-summary--editing', editing);
        editButton.hidden = editing;
        editButton.setAttribute('aria-expanded', String(editing));
        saveActions.hidden = !editing;
        extraFields.hidden = !editing;
        summaryInputs.forEach((input) => {
            input.readOnly = !editing;
            input.setAttribute('aria-readonly', String(!editing));
        });
        categories.forEach((input) => { input.disabled = !editing; });
        if (locationToggle) locationToggle.disabled = !editing;
        if (!editing) locationInput?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        if (focus) (editing ? summaryInputs[0] : editButton)?.focus();
    }
    editor.classList.add('settings-summary--enhanced');
    editButton.addEventListener('click', () => setEditing(true, true));
    cancelLink.addEventListener('click', (event) => {
        if (hasErrors) return;
        event.preventDefault();
        initialValues.forEach(({ field, value, checked }) => {
            field.value = value;
            if ('checked' in field) field.checked = checked;
        });
        setEditing(false, true);
    });
    editor.addEventListener('submit', (event) => {
        if (!editing) event.preventDefault();
    });
    setEditing(hasErrors);
    function openHashSection() {
        const section = document.getElementById(window.location.hash.slice(1));
        if (section?.matches('.settings-detail')) section.open = true;
    }
    openHashSection();
    window.addEventListener('hashchange', openHashSection);
})();
