import {
  dateYesterday,
  getData,
  getWindowHashValues,
  updateWindowHash,
  getDateValuesText,
  addDate,
} from "./module/common.js";

const table = document.getElementById('scores-table');
const datePicker = document.getElementById('date-picker');
//const dateText = document.getElementById('date-text');

const dateChangers = document.getElementsByClassName('move-day');

const updateTimeDisplay = document.getElementById('update-time-span');

function scoreLink(type, id) { 
  if (type === 'new') { 
    return `https://osu.ppy.sh/scores/${id}`;
  } 

  if (type == 'old') { 
    return `https://osu.ppy.sh/scores/fruits/${id}`;
  }
}

function dataToTableRow(data) {
  return `<tr>
    <td><a href="${data.link}" target="_new">${data.score_pp.toFixed(2)}</a></td>
    <td><img src="https://a.ppy.sh/${data.user_id}" loading="lazy"></td>
    <td>${data.user_name ?? '???'}</td>
    <td>${data.score_grade ?? '???'}</td>
    <td><img src="https://assets.ppy.sh/beatmaps/${data.beatmapset_id}/covers/list.jpg" loading="lazy"></td>
    <td>${data.beatmapset_title ?? '???'}</td>
    <td>${data.beatmap_version ?? '???'}</td>
    <td>${data.beatmap_difficulty != null ? data.beatmap_difficulty.toFixed(2) : '???'}</td>
    <td>${data.accuracy != null ? (data?.accuracy * 100).toFixed(2) : '???'}</td>
    <td>${data.max_combo ?? '???'}</td>
    <td>${data.count_miss ?? '???'}</td>
    <td>${data.score_mods}</td>
  </tr>`;
}

async function showScores(date) {
  // TODO: unify table updating, maybe?
  table.innerHTML = `<tr>
    <td colspan="12">Fetching scores for ${date}...</td>
  </tr>`;

  const records = await getData(date, 'PH-fruits-pp-records');

  if (!records) {
    table.innerHTML = `<tr>
      <td colspan="12">Cannot find data for the current date :(</td>
    </tr>`;
    return;
  }

  const dataMapping = records.map;
  const scores = records.data;

  const mapped = Object.entries(scores).map((scoreObject) => {
    const [id, values] = scoreObject;

    let obj = {
      id: id,
    };

    for (let i = 0; i < dataMapping.length; i++) { 
      let key = dataMapping[i];
      let value = values[i];
      
      obj[key] = value;
    }

    obj['link'] = scoreLink(obj['score_type'], id);

    return obj;
  });

  mapped.sort((a, b) => {
    return b.score_pp - a.score_pp;
  })

  let tableRowString = '';

  for (let data of mapped) {
    tableRowString += dataToTableRow(data);
  }

  table.innerHTML = tableRowString;

  const updateTime = new Date(records.update_date * 1000);

  updateTimeDisplay.innerHTML = `${updateTime.toDateString()} ${updateTime.toTimeString()}`;
}

// TODO: reduce code reuse, direct copy paste from main-ranking.js
function moveDates(e) {
  const dateAdditiveValue = e.target.dataset.days;

  const date = new Date(datePicker.value);

  datePicker.value = getDateValuesText(addDate(date, dateAdditiveValue));

  datePicker.dispatchEvent(new Event('change'));
}

function main() {
  const date = getDateValuesText(dateYesterday);
  const windowHash = window.location.hash.substring(1);

  datePicker.setAttribute('max', date)

  datePicker.addEventListener('change', () => {
    const dateValue = datePicker.value
    const [year, month, day] = dateValue.split('-');

    //dateText.innerHTML = `${year}-${month}-${day}`;
    showScores(`${year}/${month}/${day}`);
    updateWindowHash({ date: datePicker.value });
  });

  if (windowHash) {
    let hashValues = getWindowHashValues(windowHash);
    datePicker.value = hashValues.date ?? date;
  } else {
    datePicker.value = date;
  }

  Array.from(dateChangers).forEach((element) => {
    element.addEventListener('click', moveDates);
  });

  datePicker.dispatchEvent(new Event('change'));
}

main();