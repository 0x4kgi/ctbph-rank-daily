const table = document.getElementById('scores-table');

async function getData() { 
  const url = 'data/2024/07/12/PH-fruits-pp-records.json';

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

async function main() {
  const records = await getData();

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

main();