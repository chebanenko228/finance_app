function toggleMonthlyDate() {
  const checkbox = document.getElementById('is_monthly');
  const dateInput = document.getElementById('date');
  const dateLabel = document.getElementById('date_label');

  if (checkbox.checked) {
    dateLabel.textContent = 'Введіть перший день виплат';
  } else {
    dateLabel.textContent = 'Дата';
  }
}

window.onload = toggleMonthlyDate;
