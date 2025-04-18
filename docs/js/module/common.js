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

function getDateValuesText(date) { 
  const [year, month, day] = getDateValues(date);

  return `${year}-${month}-${day}`;
}

function minusDate(minuend, subtrahend) {
  const difference = new Date(minuend);
  difference.setDate(difference.getDate() - subtrahend);

  return difference;
}

// what the fuck
// i do not vibe with this
// TODO: make an actual date manipulation thingy PLEASE
function addDate(addend, toAdd) {
  return minusDate(addend, -toAdd);
}

function getElem(id) {
  return document.getElementById(id);
}

function getWindowHashValues(hash) {
  const hashList = hash.split(';');
  let hashPairs = {};

  hashList.forEach(item => {
    let [key, value] = item.split(':');

    hashPairs[key] = value;
  });

  return hashPairs;
}

function updateWindowHash(dataObject) {
  let hashList = Object.keys(dataObject).map(key => `${key}:${dataObject[key]}`);
  let newHash = hashList.join(';');
  window.location.hash = newHash;
}

export {
  dateToday,
  dateYesterday,
  getData,
  getDateValues,
  getDateValuesText,
  getElem,
  getWindowHashValues,
  addDate,
  minusDate,
  updateWindowHash
};