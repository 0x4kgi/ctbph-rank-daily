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

export {
  mapData,
  mapDifference,
};