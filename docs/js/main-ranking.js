import {
  dateYesterday,
  getData,
  getDateValuesText,
  getWindowHashValues,
  addDate,
  minusDate,
  updateWindowHash,
} from "./module/common.js";

import {
  mapData,
  mapDifference,
} from "./module/player-rankings.js";

const datePickerOld = document.getElementById('date-picker-old');
const datePickerNew = document.getElementById('date-picker-new');

const dateChangers = document.getElementsByClassName('move-day');

const updateTimeDisplayOld = document.getElementById('update-time-span-old');
const updateTimeDisplayNew = document.getElementById('update-time-span-new');

const mainTable = document.getElementById('ranking-table');

function resetTableForLoading(text = 'gathering data...') {
  mainTable.innerHTML = `<tr>
    <td colspan="9">${text}</td>
  </tr>`;
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

  function fNum(num, hasDecimals) {
    const options = hasDecimals ? {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    } : {};

    return num.toLocaleString(undefined, options);
  }

  function statDiffSpan(diff, hasDecimals = false) {
    if (!diff) return '';

    const fancyNum = fNum(diff, hasDecimals);

    if (!parseFloat(fancyNum)) return '';

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
        const symbol = stat === 'acc' ? '%' : '';

        let curr = stat !== 'new_entry' ? fNum(playerData[stat], hasDecimals) : 0;

        cells[stat] = `<td>${curr}${symbol}${statDiffSpan(diff[stat], hasDecimals)}</td>`
      });

      return `<tr ${trClass(diff.new_entry, diff.country_rank)}>
        ${cells.country_rank}
        <td>
          <a href="https://osu.ppy.sh/users/${playerData.user_id}/fruits" target="_new">
            <img src="https://a.ppy.sh/${playerData.user_id}" loading="lazy">
          </a>
        </td>
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

  const oldData = await getData(datePickerOld.value, 'PH-fruits');
  const newData = await getData(datePickerNew.value, 'PH-fruits');

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

  updateWindowHash({
    start: datePickerOld.value,
    end: datePickerNew.value,
  });
}

function moveDates(e) {
  const dateAdditiveValue = e.target.dataset.days;

  const oldDate = new Date(datePickerOld.value);
  const newDate = new Date(datePickerNew.value);

  datePickerOld.value = getDateValuesText(addDate(oldDate, dateAdditiveValue));
  datePickerNew.value = getDateValuesText(addDate(newDate, dateAdditiveValue));

  datePickerOld.dispatchEvent(new Event('change'));
}

function main() {
  resetTableForLoading();

  // since there is no data for the current date
  const oDate = getDateValuesText(dateYesterday);
  datePickerNew.setAttribute('max', datePickerNew.value);

  // get the date two days ago...
  const dateMinus2 = minusDate(dateYesterday, 1);
  const d2Date = getDateValuesText(dateMinus2);

  // get the window hash...
  const windowHash = window.location.hash.substring(1); // removes extra #

  if (windowHash) {
    let hashValues = getWindowHashValues(windowHash);
    
    datePickerOld.value = hashValues.start ?? d2Date;
    datePickerNew.value = hashValues.end ?? oDate;
  } else {
    datePickerOld.value = d2Date;
    datePickerNew.value = oDate;
  }

  datePickerOld.setAttribute('max', datePickerOld.value);
  datePickerNew.setAttribute('min', datePickerOld.value);

  datePickerNew.addEventListener('change', updateRanking);
  datePickerOld.addEventListener('change', updateRanking);

  Array.from(dateChangers).forEach((element) => {
    element.addEventListener('click', moveDates);
  });

  datePickerNew.dispatchEvent(new Event('change'));
}

main();
