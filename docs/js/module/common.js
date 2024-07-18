const dateToday = new Date();
const dateYesterday = new Date(dateToday);
dateYesterday.setDate(dateYesterday.getDate() - 1);

async function getData(date, file) {
  console.time(date);

  const selectedDate = new Date(date);
  const [y, m, d] = getDateValues(selectedDate);

  //const url = `data/${y}/${m}/${d}/PH-fruits.json`;
  const url = `data/${y}/${m}/${d}/${file}.json`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`[data/${y}/${m}/${d}/${file}.json] Response status: ${response.status}`);
    }

    const json = await response.json();

    console.timeEnd(date);
    return json;

  } catch (error) {
    console.error(error.message);

    return false;
  }
}

function getDateValues(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  return [year, month, day];
}

function minusDate(minuend, subtrahend) {
  const difference = new Date(minuend);
  difference.setDate(difference.getDate() - subtrahend);

  return difference;
}

export {
  dateToday,
  dateYesterday,
  getData,
  getDateValues,
  minusDate,
};