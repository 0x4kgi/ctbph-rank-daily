const table = document.getElementById('scores-table');
const datePicker = document.getElementById('date-picker');

async function getData(date) {
  const url = `data/${date}/PH-fruits-pp-records.json`;

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
    <td>${data.user_name}</td>
    <td>${data.score_grade}</td>
    <td><img src="https://assets.ppy.sh/beatmaps/${data.beatmapset_id}/covers/list.jpg" loading="lazy"></td>
    <td>${data.beatmapset_title}</td>
    <td>${data.beatmap_version}</td>
    <td>${data.beatmap_difficulty.toFixed(2)}</td>
    <td>${(data.accuracy * 100).toFixed(2)}</td>
    <td>${data.max_combo}</td>
    <td>${data.count_miss}</td>
    <td>${data.score_mods}</td>
  </tr>`;
}

async function showScores(date) {
  const records = await getData(date);

  if (!records) {
    alert('cannot get data')
    return;
  }

  const dataMapping = records.map;
  const scores = records.data;

  console.log(dataMapping);
  console.log(scores);

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
}

function main() {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const year = yesterday.getFullYear();
  const month = String(yesterday.getMonth() + 1).padStart(2, '0');
  const day = String(yesterday.getDate()).padStart(2, '0');

  datePicker.setAttribute('max', `${year}-${month}-${day}`)

  datePicker.addEventListener('change', () => {
    const dateValue = datePicker.value
    const [year, month, day] = dateValue.split('-');
    
    showScores(`${year}/${month}/${day}`);
  });

  datePicker.value = `${year}-${month}-${day}`;
  datePicker.dispatchEvent(new Event('change'));
}

main();