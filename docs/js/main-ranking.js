const dateToday = new Date();
const dateYesterday = new Date(dateToday);
dateYesterday.setDate(dateYesterday.getDate() - 1);

// TODO: unify this with pp-records.js
function getDateValues(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  return [year, month, day];
}

const datePickerOld = document.getElementById('date-picker-old');
const datePickerNew = document.getElementById('date-picker-new');

const updateTimeDisplayOld = document.getElementById('update-time-span-old');
const updateTimeDisplayNew = document.getElementById('update-time-span-new');

const mainTable = document.getElementById('ranking-table');

// TODO: unify this with pp-records.js
async function getData(date) {
  const url = `data/${date}/PH-fruits.json`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Response status: ${response.status}`);
    }

    const json = await response.json();

    return json;

  } catch (error) {
    console.error(error.message);

    return false;
  }
}


