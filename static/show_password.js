function togglePassword(checkboxId, passwordInputId) {
    const checkbox = document.getElementById(checkboxId);
    const pwdInput = document.getElementById(passwordInputId);
    if (!checkbox || !pwdInput) return;

    if (checkbox.checked) {
        pwdInput.type = 'text';
    } else {
        pwdInput.type = 'password';
    }
}
