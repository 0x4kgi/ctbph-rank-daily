import {
  dateYesterday,
  getData,
  getDateValuesText,
  getElem,
  getWindowHashValues,
  minusDate,
  addDate,
  updateWindowHash,
} from "./module/common.js";

import {
  mapData,
  mapDifference,
} from "./module/player-rankings.js";

const datePickerOld = getElem('date-picker-old');
const datePickerNew = getElem('date-picker-new');

const dateChangers = document.getElementsByClassName('move-day');

const updateTimeDisplayOld = getElem('update-time-span-old');
const updateTimeDisplayNew = getElem('update-time-span-new');

const tables = {
  accuracy: getElem('accuracy-table'),
  globalRank: getElem('global-rank-table'),
  phRank: getElem('ph-rank-table'),
  playCount: getElem('play-count-table'),
  playTime: getElem('play-time-table'),
  pp: getElem('pp-table'),
  rankedScore: getElem('ranked-score-table'),
  totalHits: getElem('total-hits-table'),
};

const mainStat = {
  accuracy: 'acc',
  globalRank: 'global_rank',
  phRank: 'country_rank',
  playCount: 'play_count',
  playTime: 'play_time',
  pp: 'pp',
  rankedScore: 'ranked_score',
  totalHits: 'total_hits',
}

function resetTableForLoading(table, text) {
  table.innerHTML = `<tr>
    <td colspan="6">${text}</td>
  </tr>`;
}

// direct translation from function with same name from data_to_html.py
function formatDuration(seconds) {
  const intervals = [
    ['d', 86400], // 60 * 60 * 24
    ['h', 3600],  // 60 * 60
    ['m', 60],
    ['s', 1],
  ];

  const result = [];
  intervals.forEach(([name, count]) => {
    const value = Math.floor(seconds / count);
    if (value) {
      result.push(`${value}${name}`);
      seconds %= count;
    }
  });

  // If seconds is less than 1 and not yet added, add it with float formatting
  if (seconds) {
    result.push(`${seconds.toFixed(2)}s`);
  }

  return result.length ? result.join(' ') : '0s';
}

// direct translation from function with same name from data_to_html.py
function simplifyNumber(num) {
  const suffixes = ['', 'k', 'M', 'B', 'T'];
  let magnitude = 0;

  while (Math.abs(num) >= 1000 && magnitude < suffixes.length - 1) {
    magnitude++;
    num /= 1000.0;
  }

  if (magnitude === 0) {
    return num.toFixed(0);
  } else {
    return `${num.toFixed(2)}${suffixes[magnitude]}`;
  }
}

// TODO: reduce code reuse, this is mostly copy pasted from main-ranking.js
function updateTable(targetTable, attribute, oldMappedData, newMappedData, dataDifference) {
  function fNum(num) {
    const hasDecimals = attribute === 'acc';

    const options = hasDecimals ? {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    } : {};

    return num.toLocaleString(undefined, options);
  }

  let rows = Object.values(dataDifference)
    .filter(item => item[attribute] > 0)
    .sort((a, b) => b[attribute] - a[attribute])
    .map(playerData => {
      const id = playerData.user_id;

      let diffOfStat = dataDifference[id][attribute];
      let oldStat = oldMappedData[id][attribute];
      let newStat = newMappedData[id][attribute];

      if (attribute === 'play_time') {
        diffOfStat = formatDuration(diffOfStat);
        oldStat = formatDuration(oldStat);
        newStat = formatDuration(newStat);
      } else if (['ranked_score', 'total_hits'].includes(attribute)) {
        diffOfStat = simplifyNumber(diffOfStat);
        oldStat = simplifyNumber(oldStat);
        newStat = simplifyNumber(newStat);
      } else {
        diffOfStat = fNum(diffOfStat);
        oldStat = fNum(oldStat);
        newStat = fNum(newStat);
      }

      return `<tr>
        <td><abbr title="${dataDifference[id][attribute]}">${diffOfStat}</abbr></td>
        <td>
          <a href="https://osu.ppy.sh/users/${playerData.user_id}/fruits" target="_new">
            <img src="https://a.ppy.sh/${playerData.user_id}" loading="lazy">
          </a>
        </td>
        <td>${playerData.ign}</td>
        <td><abbr title="${oldMappedData[id][attribute]}">${oldStat}</abbr></td>
        <td>→</td>
        <td><abbr title="${newMappedData[id][attribute]}">${newStat}</abbr></td>
      </tr>`;
    });

  if (rows.length === 0) {
    resetTableForLoading(targetTable, 'Selected time range does not have enough data, select a more recent date!')
  } else {
    targetTable.innerHTML = rows.join('');
  }

}

async function updateRanking() {

  // TODO: reduce code reuse, this is copy pasted from main-ranking.js
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

  const oldMappedData = mapData(oldData);
  const newMappedData = mapData(newData);

  const dataDifference = mapDifference(oldMappedData, newMappedData);

  for (let table in tables) {
    resetTableForLoading(tables[table], 'Parsing values for this stat...');
    updateTable(tables[table], mainStat[table], oldMappedData, newMappedData, dataDifference);
  }

  updateWindowHash({
    start: datePickerOld.value,
    end: datePickerNew.value,
  });
}

// TODO: reduce code reuse, direct copy paste from main-ranking.js
function moveDates(e) {
  const dateAdditiveValue = e.target.dataset.days;

  const oldDate = new Date(datePickerOld.value);
  const newDate = new Date(datePickerNew.value);

  datePickerOld.value = getDateValuesText(addDate(oldDate, dateAdditiveValue));
  datePickerNew.value = getDateValuesText(addDate(newDate, dateAdditiveValue));

  datePickerOld.dispatchEvent(new Event('change'));
}

// TODO: unify this with main-ranking.js
function main() {
  for (let table in tables) {
    resetTableForLoading(tables[table], 'Initializing...');
  }

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

main()