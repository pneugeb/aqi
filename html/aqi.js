const aqiHist = {
  maxRows: 100,
  data: [],
  idx0: 0,
  idxMax: 1
};

//const log_dir = "/logs/";
const log_dir = "";

const max_num_logs = 24;

let log_index = 0;

function getData() {
  fetch("aqi.json").then(response => {
    response.json().then(data => {
      //console.log(data);
      updateHtml(data[data.length-1]);
    })
  }).catch(err => {
    console.log(err);
  })
}

function getHistoryData() {
  fetch("aqi.json").then(response => {
    response.json().then(data => {
      //console.log(data);
      aqiHist.data = data;
      aqiHist.idxMax = aqiHist.data.length;
      aqiHist.idx0 = aqiHist.idxMax - aqiHist.maxRows;
      if(aqiHist.idx0 < 0) {
        aqiHist.idx0 = 0;
      }
      updateHistoryHtml();
    })
  }).catch(err => {
    console.log(err);
  })
}

function log_page_back() {
  log_index--;
  if(log_index < 0) {
    log_index = 0;
  }
  //console.log("page back " + log_index);
  getLogData();
}

function log_page_forward() {
  log_index++;
  if(log_index > (max_num_logs - 1)) {
    log_index = max_num_logs - 1;
  }
  //console.log("page forward " + log_index);
  getLogData();
}

function getLogData() {
  //console.log("setting log_path, index: " + log_index);
  switch(log_index) {
    case 0:
      log_path = log_dir + "aqi.log";
      break;
    default:
      log_path = log_dir + "aqi.log." + log_index;
  }
  fetch(log_path).then(response => {
    response.text().then(data => {
      //console.log(data)
      updateLogHtml(data);
    })
  }).catch(err => {
    console.log(err);
  })
}

function updateHtml(data) {
  let aqiPm25 = calcAQIpm25(data.pm25);
  let aqiPm10 = calcAQIpm10(data.pm10);
  let formattedDbSize = calcDBsize(data.db_size)

  //update HTML
  document.getElementById("time").innerHTML = data.time;
  document.getElementById("aqiPm25").innerHTML = aqiPm25;
  document.getElementById("aqiPm10").innerHTML = aqiPm10;
  document.getElementById("pm25").innerHTML = "(PM2.5: " + data.pm25 + " µg/m³)";
  document.getElementById("pm10").innerHTML = "(PM10: " + data.pm10 + " µg/m³)";
  document.getElementById("aqiLpsTemp").innerHTML = data.lps_temp;
  document.getElementById("aqiLpsPressure").innerHTML = data.lps_pressure;
  document.getElementById("lpsTemp").innerHTML = "(Temp: " + data.lps_temp + " °C)";
  document.getElementById("lpsPressure").innerHTML = "(Pressure: " + data.lps_pressure + " hPa)";
  document.getElementById("aqiDhtTemp").innerHTML = data.dht_temp;
  document.getElementById("aqiDhtHumidity").innerHTML = data.dht_humidity;
  document.getElementById("dhtTemp").innerHTML = "(Temp: " + data.dht_temp + " °C)";
  document.getElementById("dhtHumidity").innerHTML = "(Humidity: " + data.dht_humidity + " %)";
  document.getElementById("db_size").innerHTML = "Database size: " + formattedDbSize;

  //set colors
  colorsPm25 = getColor(aqiPm25);
  colorsPm10 = getColor(aqiPm10);
  document.getElementById("containerPm25").style.background = colorsPm25.bg;
  document.getElementById("containerPm25").style.color = colorsPm25.text
  document.getElementById("containerPm10").style.background = colorsPm10.bg;
  document.getElementById("containerPm10").style.color = colorsPm10.text
}

function updateHistoryHtml() {
  document.getElementById("historyTable").innerHTML = "";

  aqiHist.idxMax = aqiHist.idx0 + aqiHist.maxRows;
  if(aqiHist.idxMax > aqiHist.data.length) {
    aqiHist.idxMax = aqiHist.data.length;
  }
  document.getElementById("currentRowsPage").innerHTML =
    `rows ${aqiHist.idx0 + 1} to ${aqiHist.idxMax} of ${aqiHist.data.length}`;
  for(let idx = aqiHist.idx0; idx < aqiHist.idxMax; idx++) {
    let eRow = document.createElement("tr");

    let data = aqiHist.data[idx];
    let aqiPm25 = calcAQIpm25(data.pm25);
    let aqiPm10 = calcAQIpm10(data.pm10);

    let eTime = document.createElement("td");
    eTime.innerHTML = data.time;
    eRow.append(eTime);

    let ePm25 = document.createElement("td");
    ePm25.innerHTML = data.pm25;
    eRow.append(ePm25);

    let eAqiPm25 = document.createElement("td");
    eAqiPm25.innerHTML = aqiPm25;
    eRow.append(eAqiPm25);

    let ePm10 = document.createElement("td");
    ePm10.innerHTML = data.pm10;
    eRow.append(ePm10);

    let eAqiPm10 = document.createElement("td");
    eAqiPm10.innerHTML = aqiPm10;
    eRow.append(eAqiPm10);

    let eLpsTemp = document.createElement("td");
    eLpsTemp.innerHTML = data.lps_temp;
    eRow.append(eLpsTemp);

    let eLpsPressure = document.createElement("td");
    eLpsPressure.innerHTML = data.lps_pressure;
    eRow.append(eLpsPressure);

    let eDhtTemp = document.createElement("td");
    eDhtTemp.innerHTML = data.dht_temp;
    eRow.append(eDhtTemp);

    let eDhtHumidity = document.createElement("td");
    eDhtHumidity.innerHTML = data.dht_humidity;
    eRow.append(eDhtHumidity);

    let colorsPm25 = getColor(aqiPm25);
    let colorsPm10 = getColor(aqiPm10);

    ePm25.style.background = colorsPm25.bg;
    ePm25.style.color = colorsPm25.text
    eAqiPm25.style.background = colorsPm25.bg;
    eAqiPm25.style.color = colorsPm25.text
    ePm10.style.background = colorsPm10.bg;
    ePm10.style.color = colorsPm10.text
    eAqiPm10.style.background = colorsPm10.bg;
    eAqiPm10.style.color = colorsPm10.text

    document.getElementById("historyTable").append(eRow);
  }
}

function showPrevHistory() {
  if(aqiHist.idx0 > 0) {
    aqiHist.idx0 = aqiHist.idx0 - aqiHist.maxRows;
  }
  if(aqiHist.idx0 < 0) {
    aqiHist.idx0 = 0;
  }

  updateHistoryHtml();
}

function showNextHistory() {
  if(aqiHist.idx0 < aqiHist.data.length) {
    aqiHist.idx0 = aqiHist.idx0 + aqiHist.maxRows;
  }
  if(aqiHist.idx0 > aqiHist.data.length - aqiHist.maxRows) {
    aqiHist.idx0 = aqiHist.data.length - aqiHist.maxRows;
  }

  updateHistoryHtml();
}

function updateLogHtml(logs) {
  document.getElementById("logName").innerHTML = (function() {
    switch(log_index) {
      case 0:
        return "aqi.log";
      default:
        return "aqi.log." + log_index;
    }
  })();
  document.getElementById("log").innerHTML = logs;
}

function getColor(aqi) {
  switch (true) {
    case (aqi >= 50 && aqi < 100):
      color = "yellow";
      break;
    case (aqi >= 100 && aqi < 150):
      color = "orange";
      break;
    case (aqi >= 150 && aqi < 200):
      color = "red";
      break;
    case (aqi >= 200 && aqi < 300):
      color = "purple";
      break;
    case (aqi >= 300):
      color = "brown";
      break;
    default:
      color = "Lime";
  }
  return {bg: color, text: (aqi > 200) ? "white" : "black"};
}

function calcAQIpm25(pm25) {
  let pm1 = 0;
	let pm2 = 12;
	let pm3 = 35.4;
	let pm4 = 55.4;
	let pm5 = 150.4;
	let pm6 = 250.4;
	let pm7 = 350.4;
	let pm8 = 500.4;

	let aqi1 = 0;
	let aqi2 = 50;
	let aqi3 = 100;
	let aqi4 = 150;
	let aqi5 = 200;
	let aqi6 = 300;
	let aqi7 = 400;
	let aqi8 = 500;

	let aqipm25 = 0;

	if (pm25 >= pm1 && pm25 <= pm2) {
		aqipm25 = ((aqi2 - aqi1) / (pm2 - pm1)) * (pm25 - pm1) + aqi1;
	} else if (pm25 >= pm2 && pm25 <= pm3) {
		aqipm25 = ((aqi3 - aqi2) / (pm3 - pm2)) * (pm25 - pm2) + aqi2;
	} else if (pm25 >= pm3 && pm25 <= pm4) {
		aqipm25 = ((aqi4 - aqi3) / (pm4 - pm3)) * (pm25 - pm3) + aqi3;
	} else if (pm25 >= pm4 && pm25 <= pm5) {
		aqipm25 = ((aqi5 - aqi4) / (pm5 - pm4)) * (pm25 - pm4) + aqi4;
	} else if (pm25 >= pm5 && pm25 <= pm6) {
		aqipm25 = ((aqi6 - aqi5) / (pm6 - pm5)) * (pm25 - pm5) + aqi5;
	} else if (pm25 >= pm6 && pm25 <= pm7) {
		aqipm25 = ((aqi7 - aqi6) / (pm7 - pm6)) * (pm25 - pm6) + aqi6;
	} else if (pm25 >= pm7 && pm25 <= pm8) {
		aqipm25 = ((aqi8 - aqi7) / (pm8 - pm7)) * (pm25 - pm7) + aqi7;
	}
	return aqipm25.toFixed(0);
}

function calcAQIpm10(pm10) {
	let pm1 = 0;
	let pm2 = 54;
	let pm3 = 154;
	let pm4 = 254;
	let pm5 = 354;
	let pm6 = 424;
	let pm7 = 504;
	let pm8 = 604;

	let aqi1 = 0;
	let aqi2 = 50;
	let aqi3 = 100;
	let aqi4 = 150;
	let aqi5 = 200;
	let aqi6 = 300;
	let aqi7 = 400;
	let aqi8 = 500;

	let aqipm10 = 0;

	if (pm10 >= pm1 && pm10 <= pm2) {
		aqipm10 = ((aqi2 - aqi1) / (pm2 - pm1)) * (pm10 - pm1) + aqi1;
	} else if (pm10 >= pm2 && pm10 <= pm3) {
		aqipm10 = ((aqi3 - aqi2) / (pm3 - pm2)) * (pm10 - pm2) + aqi2;
	} else if (pm10 >= pm3 && pm10 <= pm4) {
		aqipm10 = ((aqi4 - aqi3) / (pm4 - pm3)) * (pm10 - pm3) + aqi3;
	} else if (pm10 >= pm4 && pm10 <= pm5) {
		aqipm10 = ((aqi5 - aqi4) / (pm5 - pm4)) * (pm10 - pm4) + aqi4;
	} else if (pm10 >= pm5 && pm10 <= pm6) {
		aqipm10 = ((aqi6 - aqi5) / (pm6 - pm5)) * (pm10 - pm5) + aqi5;
	} else if (pm10 >= pm6 && pm10 <= pm7) {
		aqipm10 = ((aqi7 - aqi6) / (pm7 - pm6)) * (pm10 - pm6) + aqi6;
	} else if (pm10 >= pm7 && pm10 <= pm8) {
		aqipm10 = ((aqi8 - aqi7) / (pm8 - pm7)) * (pm10 - pm7) + aqi7;
	}
	return aqipm10.toFixed(0);
}

function calcDBsize(dbSize) {
  switch (true) {
    case ((dbSize/1024) < 1):
      size = (dbSize) + "B"
      break;
    case ((dbSize/(1024**2)) < 1):
      size = (dbSize/(1024**1)).toFixed(2) + "KiB"
      break;
    case ((dbSize/(1024**3)) < 1):
      size = (dbSize/(1024**2)).toFixed(2) + "MiB"
      break;
    default:
      size = (dbSize/(1024**3)).toFixed(2) + "GiB"
  }
  return size;
}