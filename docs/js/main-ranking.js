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
  console.time(date);

  const selectedDate = new Date(date);
  const [y, m, d] = getDateValues(selectedDate);

  const url = `data/${y}/${m}/${d}/PH-fruits.json`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`[data/${y}/${m}/${d}/PH-fruits.json] Response status: ${response.status}`);
    }

    const json = await response.json();

    console.timeEnd(date);
    return json;

  } catch (error) {
    console.error(error.message);

    return false;
  }
}

function resetTableForLoading(text = 'gathering data...') {
  mainTable.innerHTML = `<tr>
    <td colspan="9">${text}</td>
  </tr>`;
}

function minusDate(minuend, subtrahend) {
  const difference = new Date(minuend);
  difference.setDate(difference.getDate() - subtrahend);

  return difference;
}

function mapData(data) {
  console.time('mapData');

  const mapping = data.map;
  const values = data.data;

  let obj = {};

  const mapped = Object.entries(values).map((playerObject) => {
    const [userId, values] = playerObject;

    obj[userId] = {
      user_id: userId,
    };

    for (let i = 0; i < mapping.length; i++) {
      let key = mapping[i];
      let value = values[i];

      obj[userId][key] = value;
    }
  });

  console.timeEnd('mapData');
  return obj;
}

function mapDifference(oldData, newData) {
  console.time('mapDifference');

  let diff = {};

  for (const key in newData) {
    let values = newData[key];

    diff[key] = {
      new_entry: false,
    };

    if (!oldData[key]) { 
      diff[key]['new_entry'] = true;
    }

    for (const attribute in values) {
      if (attribute === 'ign' || attribute === 'user_id') continue;

      if (diff[key]['new_entry']) {
        diff[key][attribute] = 0;
      } else { 
        diff[key][attribute] = newData[key][attribute] - oldData[key][attribute];
      }
    }

    diff[key]['country_rank'] = 0 - diff[key]['country_rank'];
    diff[key]['global_rank'] = 0 - diff[key]['global_rank'];
    diff[key]['ign'] = newData[key]['ign'];
    diff[key]['user_id'] = newData[key]['user_id'];
  }

  console.timeEnd('mapDifference');
  return diff;
}

function updateTable(newMappedData, dataDifference) {
  function getDiff(id, attr) {
    return dataDifference[id][attr];
  }

  function trClass(isNew, diff) {
    if (isNew) {
      return 'class="new-entry"';
    }

    if (diff > 0) {
      return 'class="rank-up"'
    }

    if (diff < 0) {
      return 'class="rank-down"'
    }

    return '';
  }

  function fnum(num, hasDecimals) {
    const options = hasDecimals ? {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    } : {};

    return num.toLocaleString(undefined, options);
  }

  function statDiffspan(diff, hasDecimals = false) {
    if (!diff) return '';

    const fancyNum = fnum(diff, hasDecimals);
    const prefix = diff > 0 ? '+' : '';
    const supClass = diff > 0 ? 'increase' : 'decrease';

    return `<sup class="${supClass}">${prefix}${fancyNum}</sup>`;
  }

  const stats = [
    'new_entry',
    'country_rank',
    'pp',
    'acc',
    'play_count',
    'rank_x',
    'rank_s',
    'rank_a',
  ];

  let rows = Object.values(newMappedData)
    .sort((a, b) => a.country_rank - b.country_rank)
    .map(playerData => {
      const id = playerData.user_id;

      const diff = {};
      const cells = {};
      
      stats.forEach(stat => {
        diff[stat] = getDiff(id, stat);

        const hasDecimals = stat === 'acc';

        let curr = stat !== 'new_entry' ? fnum(playerData[stat], hasDecimals) : 0;

        cells[stat] = `<td>${curr}${statDiffspan(diff[stat], hasDecimals)}</td>`
      });

      return `<tr ${trClass(diff.new_entry, diff.country_rank)}>
        ${cells.country_rank}
        <td><img src="https://a.ppy.sh/${playerData.user_id}" loading="lazy"></td>
        <td>${playerData.ign}</td>
        ${cells.pp}
        ${cells.acc}
        ${cells.play_count}
        ${cells.rank_x}
        ${cells.rank_s}
        ${cells.rank_a}
      </tr>`;
    });

  mainTable.innerHTML = rows.join('');
}

async function updateRanking() {
  resetTableForLoading(`Loading data from ${datePickerOld.value} to ${datePickerNew.value}...`);

  const oldDate = new Date(datePickerOld.value);
  const newDate = new Date(datePickerNew.value);

  if (oldDate > newDate) {
    resetTableForLoading(`Date order flipped, check inputs. old: ${datePickerOld.value}, new: ${datePickerNew.value}`);
    return;
  }

  datePickerNew.setAttribute('min', datePickerOld.value);
  datePickerOld.setAttribute('max', datePickerNew.value);

  const oldData = await getData(datePickerOld.value);
  const newData = await getData(datePickerNew.value);

  if (!oldData || !newData) {
    resetTableForLoading(`Incomplete data. old: ${datePickerOld.value}, new: ${datePickerNew.value}`);
    return;
  }

  const oldUpdateTime = new Date(oldData.update_date * 1000);
  const newUpdateTime = new Date(newData.update_date * 1000);

  updateTimeDisplayOld.innerHTML = `${oldUpdateTime.toDateString()} ${oldUpdateTime.toTimeString()}`;
  updateTimeDisplayNew.innerHTML = `${newUpdateTime.toDateString()} ${newUpdateTime.toTimeString()}`;

  resetTableForLoading(`Data loaded! Now parsing ${datePickerOld.value} to ${datePickerNew.value}. Please wait for a bit!`);

  const oldMappedData = mapData(oldData);
  const newMappedData = mapData(newData);

  const dataDifference = mapDifference(oldMappedData, newMappedData);

  updateTable(newMappedData, dataDifference);
}

function main() {
  resetTableForLoading();

  // since there is no data for the current date
  const [oYear, oMonth, oDay] = getDateValues(dateYesterday);
  datePickerNew.value = `${oYear}-${oMonth}-${oDay}`;
  datePickerNew.setAttribute('max', datePickerNew.value);

  // get the date two days ago...
  const dateMinus2 = minusDate(dateYesterday, 1);
  const [d2Year, d2Month, d2Day] = getDateValues(dateMinus2);
  datePickerOld.value = `${d2Year}-${d2Month}-${d2Day}`;
  datePickerOld.setAttribute('max', datePickerOld.value);
  datePickerNew.setAttribute('min', datePickerOld.value);

  datePickerNew.addEventListener('change', updateRanking);
  datePickerOld.addEventListener('change', updateRanking);

  datePickerNew.dispatchEvent(new Event('change'));
}

main();
