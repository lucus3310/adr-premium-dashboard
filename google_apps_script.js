// ==========================================
// 全局配置參數
// ==========================================
var CLOUDFLARE_WORKER_URL = "https://polished-paper-a7b8.lou2739994.workers.dev/"; 
var TELEGRAM_BOT_TOKEN    = "8606716083:AAGb1UqIoOLY8xMY7rRP7OTRG-nBQXnY3lg"; 
var TELEGRAM_CHAT_ID      = "1411217775";
var TELEGRAM_MINIAPP_URL  = "https://lucus3310.github.io/adr-premium-dashboard/miniapp.html";

// ⚠️ 安全總開關：實盤下單開關 (false = 僅模擬紀錄，不花真錢 / true = 真實下單)
var ENABLE_LIVE_TRADING   = false;

// ==========================================
// Mini App API 接口 (所見即所得，零時區偏差，含 yyyy- 年份)
// ==========================================
function doGet(e) {
  var action = e.parameter.action;
  var limit = parseInt(e.parameter.limit || "1440", 10);
  
  if (action === "getData") {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("獨立欄位數據庫");
    
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "找不到【獨立欄位數據庫】工作表"
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        data: []
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    var startRow = Math.max(2, lastRow - limit + 1);
    var numRows = lastRow - startRow + 1;
    var rawData = sheet.getRange(startRow, 1, numRows, 10).getDisplayValues();
    
    var result = [];
    for (var i = 0; i < rawData.length; i++) {
      var row = rawData[i];
      if (row[0]) {
        result.push({
          time: row[0].toString().trim(),
          skhy: row[1],
          skhyDr: row[2],
          skhyLocal: row[3],
          oil: row[4],
          brent: row[5],
          wti: row[6],
          metal: row[7],
          gold: row[8],
          silver: row[9]
        });
      }
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      data: result
    })).setMimeType(ContentService.MimeType.JSON);
  }
  
  return ContentService.createTextOutput("Quant API Server Active").setMimeType(ContentService.MimeType.TEXT);
}

// ==========================================
// 核心計時任務：1分鐘監控、100%純幣安官方數據與實盤持倉比對
// ==========================================
function checkAndSendSignals() {
  var skhyDr    = GET_FUTURES_PRICE("SKHYUSDT");
  var skhyLocal = GET_FUTURES_PRICE("SKHYNIXUSDT");
  var brent     = GET_FUTURES_PRICE("BZUSDT");
  var wti       = GET_FUTURES_PRICE("CLUSDT");
  var gold      = GET_FUTURES_PRICE("XAUUSDT");
  var silver    = GET_FUTURES_PRICE("XAGUSDT");

  if (typeof skhyDr !== 'number' || typeof skhyLocal !== 'number' ||
      typeof brent !== 'number' || typeof wti !== 'number' ||
      typeof gold !== 'number' || typeof silver !== 'number') {
    Logger.log("⚠️ 價格抓取未全數完成，跳過本輪");
    return;
  }

  var skhyPrem   = parseFloat((((skhyDr / 0.1) / skhyLocal - 1) * 100).toFixed(2));
  var oilSpread  = parseFloat((brent - wti).toFixed(2));
  var metalRatio = parseFloat((gold / silver).toFixed(2));

  var now = new Date();
  var nowStr = Utilities.formatDate(now, "Asia/Taipei", "yyyy-MM-dd HH:mm:ss");

  // 1. 寫入獨立欄位數據庫
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("獨立欄位數據庫");
  if (sheet) {
    var minStr = Utilities.formatDate(now, "Asia/Taipei", "yyyy-MM-dd HH:mm");
    sheet.appendRow([minStr, skhyPrem, skhyDr, skhyLocal, oilSpread, brent, wti, metalRatio, gold, silver]);
  }

  // 2. 💼 讀取幣安實盤當前持倉與開倉價差對比
  var positionSection = formatBinancePositionSection(skhyPrem, oilSpread);

  // 3. 🟢 100% 原汁原味經典多資產監控看板 (純幣安數據)
  var broadcastMsg = "📊 <b>【多資產即時監控看板】</b>\n" +
                     "------------------------------------\n" +
                     "🔹 SK海力士溢價：" + (skhyPrem >= 0 ? "+" : "") + skhyPrem + "% ($" + skhyDr + " / $" + skhyLocal + ")\n" +
                     "🔹 原油價差：" + (oilSpread >= 0 ? "+" : "") + "$" + oilSpread.toFixed(2) + " ($" + brent + " / $" + wti + ")\n" +
                     "🔹 金銀比：" + metalRatio.toFixed(2) + "x ($" + gold + " / $" + silver + ")\n" +
                     "------------------------------------\n" +
                     positionSection + "\n" +
                     "------------------------------------\n" +
                     "⏰ 更新時間：" + nowStr;

  sendTelegramNotificationWithButton(broadcastMsg);

  // 4. 原油價差下單對沖觸發 (BZ-CL <= 2.2 USD)
  var props = PropertiesService.getScriptProperties();
  var currentOilPosition = props.getProperty("OIL_POSITION") || "NONE";

  if (oilSpread <= 2.20 && currentOilPosition === "NONE") {
    var msgOil = "🚨 <b>【原油價差對沖進場下單觸發】</b> 🚨\n" +
                 "⏰ 時間：" + nowStr + "\n" +
                 "📊 當前 Brent-WTI 價差：" + oilSpread.toFixed(2) + " USD (已低於 2.20)\n" +
                 "⚡ 執行策略：做多 Brent (BZUSDT) / 做空 WTI (CLUSDT)";
    
    sendTelegramNotificationWithButton(msgOil);
    props.setProperty("OIL_POSITION", "HOLDING");

    if (ENABLE_LIVE_TRADING) {
      sendBinanceFuturesOrder("BZUSDT", "BUY", 1);
      sendBinanceFuturesOrder("CLUSDT", "SELL", 1);
    }
  } else if (oilSpread >= 3.50 && currentOilPosition === "HOLDING") {
    var msgOilExit = "🎉 <b>【原油價差對沖獲利平倉觸發】</b> 🎉\n" +
                     "⏰ 時間：" + nowStr + "\n" +
                     "📊 當前價差：" + oilSpread.toFixed(2) + " USD (已獲利擴張至 3.50)\n" +
                     "🔒 執行動作：雙向平倉離場";
    
    sendTelegramNotificationWithButton(msgOilExit);
    props.setProperty("OIL_POSITION", "NONE");

    if (ENABLE_LIVE_TRADING) {
      sendBinanceFuturesOrder("BZUSDT", "SELL", 1);
      sendBinanceFuturesOrder("CLUSDT", "BUY", 1);
    }
  }
}

// ==========================================
// 價格抓取自訂函數 (帶入 API Key 認證，100% 抓取幣安官方期貨現價)
// ==========================================
function GET_FUTURES_PRICE(symbol) {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("BINANCE_API_KEY") || "";

  try {
    var baseUrl = CLOUDFLARE_WORKER_URL.replace(/\/+$/, "");
    var url = baseUrl + "/?symbol=" + symbol;
    var options = {
      method: "get",
      muteHttpExceptions: true,
      headers: { "X-MBX-APIKEY": apiKey.trim() }
    };

    var response = UrlFetchApp.fetch(url, options);
    var json = JSON.parse(response.getContentText());
    if (json && json.price && !isNaN(parseFloat(json.price))) {
      return parseFloat(json.price);
    }
  } catch (e) {
    Logger.log("抓取 " + symbol + " 失敗: " + e.toString());
  }
  return "抓取失敗";
}

// ==========================================
// 💼 幣安實盤持倉查詢 (經由 Worker 代理傳輸)
// ==========================================
function getBinancePositions() {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("BINANCE_API_KEY");
  var secretKey = props.getProperty("BINANCE_SECRET_KEY");

  if (!apiKey || !secretKey) {
    return [];
  }

  try {
    var timestamp = new Date().getTime();
    var queryString = "timestamp=" + timestamp;
    var signature = generateBinanceSignature(queryString, secretKey);
    
    var baseUrl = CLOUDFLARE_WORKER_URL.replace(/\/+$/, "");
    var url = baseUrl + "/proxy/binance/fapi/v2/positionRisk?" + queryString + "&signature=" + signature;

    var response = UrlFetchApp.fetch(url, {
      method: "get",
      headers: { "X-MBX-APIKEY": apiKey.trim() },
      muteHttpExceptions: true
    });

    if (response.getResponseCode() === 200) {
      var json = JSON.parse(response.getContentText());
      if (Array.isArray(json)) {
        return json.filter(function(item) {
          return parseFloat(item.positionAmt) !== 0;
        });
      }
    } else {
      Logger.log("持倉查詢失敗 (HTTP " + response.getResponseCode() + "): " + response.getContentText());
    }
  } catch (e) {
    Logger.log("getBinancePositions 例外: " + e.toString());
  }
  return [];
}

function formatBinancePositionSection(currentSkhyPrem, currentOilSpread) {
  var positions = getBinancePositions();

  if (!positions || positions.length === 0) {
    return "💼 <b>【幣安實盤持倉】</b>：當前無開倉持倉 (觀望中)";
  }

  var lines = ["💼 <b>【幣安實盤持倉與開倉價差對比】</b>"];
  var totalPnl = 0;
  var bzPos = null;
  var clPos = null;

  for (var i = 0; i < positions.length; i++) {
    var p = positions[i];
    var amt = parseFloat(p.positionAmt);
    var entry = parseFloat(p.entryPrice);
    var mark = parseFloat(p.markPrice);
    var pnl = parseFloat(p.unRealizedProfit);
    totalPnl += pnl;

    var isLong = amt > 0;
    var sideIcon = isLong ? "🟢" : "🔴";
    var sideText = isLong ? "多" : "空";
    lines.push(sideIcon + " <b>" + p.symbol + "</b> (" + sideText + "): " + (isLong ? "+" : "") + amt + "張 | 開倉: $" + entry.toFixed(2) + " | 現價: $" + mark.toFixed(2));

    if (p.symbol === "BZUSDT") bzPos = p;
    if (p.symbol === "CLUSDT") clPos = p;
  }

  // 🎯 計算開倉時原油價差與盈虧變動
  if (bzPos && clPos) {
    var bzEntry = parseFloat(bzPos.entryPrice);
    var clEntry = parseFloat(clPos.entryPrice);
    var entrySpread = bzEntry - clEntry;
    var spreadDiff = currentOilSpread - entrySpread;

    lines.push("🎯 <b>開倉時原油價差</b>：" + entrySpread.toFixed(2) + " USD ➔ <b>當前價差</b>：" + currentOilSpread.toFixed(2) + " USD (" + (spreadDiff >= 0 ? "+" : "") + spreadDiff.toFixed(2) + " USD)");
  }

  lines.push("💰 <b>持倉未實現總盈虧</b>：" + (totalPnl >= 0 ? "+" : "") + totalPnl.toFixed(2) + " USDT");

  return lines.join("\n");
}

// ==========================================
// 🔍 幣安持倉與 API 連線診斷工具 (詳細 Console 控制台 Log 輸出)
// ==========================================
function debugBinanceConnection() {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("BINANCE_API_KEY");
  var secretKey = props.getProperty("BINANCE_SECRET_KEY");

  Logger.log("=== 幣安連線與持倉診斷 ===");
  Logger.log("API Key 存在: " + (apiKey ? "YES (長度 " + apiKey.trim().length + ")" : "NO (未設定)"));
  Logger.log("Secret Key 存在: " + (secretKey ? "YES (長度 " + secretKey.trim().length + ")" : "NO (未設定)"));

  if (!apiKey || !secretKey) {
    Logger.log("❌ 腳本屬性中未設定 BINANCE_API_KEY 或 SECRET_KEY");
    return;
  }

  var timestamp = new Date().getTime();
  var queryString = "timestamp=" + timestamp;
  var signature = generateBinanceSignature(queryString, secretKey);

  var baseUrl = CLOUDFLARE_WORKER_URL.replace(/\/+$/, "");
  var url = baseUrl + "/proxy/binance/fapi/v2/positionRisk?" + queryString + "&signature=" + signature;

  try {
    var res = UrlFetchApp.fetch(url, {
      method: "get",
      headers: { "X-MBX-APIKEY": apiKey.trim() },
      muteHttpExceptions: true
    });

    var status = res.getResponseCode();
    var text = res.getContentText();
    Logger.log("HTTP 狀態碼: " + status);
    Logger.log("幣安 API 回傳內容 (前 300 字): " + text.substring(0, 300));

    if (status === 200) {
      var json = JSON.parse(text);
      if (Array.isArray(json)) {
        var active = json.filter(function(item) { return parseFloat(item.positionAmt) !== 0; });
        Logger.log("未平倉持倉張數: " + active.length);
        if (active.length > 0) {
          Logger.log("🟢 檢測到持倉詳情: " + JSON.stringify(active));
        } else {
          Logger.log("💡 幣安 API 連線成功！回傳陣列正常，但當前帳戶內【零持倉 (無未平倉單)】。");
        }
      }
    }
  } catch (e) {
    Logger.log("❌ 診斷例外錯誤: " + e.toString());
  }
}

// ==========================================
// Telegram 測試連線工具 (附帶 Mini App 按鈕)
// ==========================================
function testTelegramBot() {
  sendTelegramNotificationWithButton("🧪 <b>【Telegram 機器人測試】</b>\n100% 純幣安官方數據連線成功！");
}

function escapeHtml(text) {
  if (!text) return "";
  return text.toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ==========================================
// Telegram 附帶 Mini App 互動按鈕推播函數
// ==========================================
function sendTelegramNotificationWithButton(text) {
  var url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage";
  var payload = {
    chat_id: TELEGRAM_CHAT_ID,
    text: text,
    parse_mode: "HTML",
    reply_markup: {
      inline_keyboard: [
        [
          {
            text: "📊 開啟即時儀表板 (Mini App)",
            web_app: { url: TELEGRAM_MINIAPP_URL }
          }
        ]
      ]
    }
  };
  try {
    UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
  } catch (e) {
    Logger.log("Telegram 推播例外: " + e.toString());
  }
}

// ==========================================
// 幣安期貨下單與簽名函數
// ==========================================
function sendBinanceFuturesOrder(symbol, side, quantity) {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("BINANCE_API_KEY");
  var secretKey = props.getProperty("BINANCE_SECRET_KEY");

  if (!apiKey || !secretKey) {
    sendTelegramNotificationWithButton("❌ 下單失敗：腳本屬性中未設定 BINANCE_API_KEY 或 SECRET_KEY");
    return;
  }

  var timestamp = new Date().getTime();
  var queryString = "symbol=" + symbol + "&side=" + side + "&type=MARKET&quantity=" + quantity + "&timestamp=" + timestamp;
  var signature = generateBinanceSignature(queryString, secretKey);
  
  var baseUrl = CLOUDFLARE_WORKER_URL.replace(/\/+$/, "");
  var url = baseUrl + "/proxy/binance/fapi/v1/order?" + queryString + "&signature=" + signature;

  try {
    var response = UrlFetchApp.fetch(url, {
      method: "post",
      headers: { "X-MBX-APIKEY": apiKey.trim() },
      muteHttpExceptions: true
    });
    
    var resText = response.getContentText();
    sendTelegramNotificationWithButton("📄 幣安下單回應: " + escapeHtml(resText));
  } catch (e) {
    sendTelegramNotificationWithButton("❌ 執行下單異常: " + escapeHtml(e.toString()));
  }
}

function generateBinanceSignature(queryString, secretKey) {
  var signatureBytes = Utilities.computeHmacSha256Signature(queryString, secretKey);
  return signatureBytes.map(function(byte) {
    var v = (byte < 0) ? (byte + 256) : byte;
    return ("0" + v.toString(16)).slice(-2);
  }).join("");
}

// ==========================================
// 幣安 API 測試連線
// ==========================================
function testBinanceConnection() {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("BINANCE_API_KEY");
  var secretKey = props.getProperty("BINANCE_SECRET_KEY");

  if (!apiKey || !secretKey) {
    sendTelegramNotificationWithButton("❌ 連線測試失敗：尚未設定 API Key 與 Secret Key");
    return;
  }

  var timestamp = new Date().getTime();
  var queryString = "timestamp=" + timestamp;
  var signature = generateBinanceSignature(queryString, secretKey);
  
  var baseUrl = CLOUDFLARE_WORKER_URL.replace(/\/+$/, "");
  var url = baseUrl + "/proxy/binance/fapi/v2/balance?" + queryString + "&signature=" + signature;

  try {
    var response = UrlFetchApp.fetch(url, {
      method: "get",
      headers: { "X-MBX-APIKEY": apiKey.trim() },
      muteHttpExceptions: true
    });

    var status = response.getResponseCode();
    var resText = response.getContentText();
    
    if (status === 200) {
      var json = JSON.parse(resText);
      if (Array.isArray(json)) {
        var usdtObj = json.find(function(item) { return item.asset === "USDT"; });
        var balance = usdtObj ? usdtObj.balance : "未知";
        sendTelegramNotificationWithButton("🟢 <b>【幣安期貨 API 連線成功】</b>\n💰 USDT 帳戶餘額：" + balance + " USDT");
      } else {
        sendTelegramNotificationWithButton("📄 幣安回應內容: " + escapeHtml(resText));
      }
    } else {
      sendTelegramNotificationWithButton("❌ 連線失敗 (HTTP " + status + "): " + escapeHtml(resText));
    }
  } catch (e) {
    sendTelegramNotificationWithButton("❌ 執行例外異常: " + escapeHtml(e.toString()));
  }
}

// ==========================================
// 歷史數據補齊工具
// ==========================================
function backfillMissingData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("獨立欄位數據庫");
  if (!sheet) return;
  
  var limit = 300;
  var skhyDrData = fetchBinanceKlines("SKHYUSDT", limit);
  var skhyLocalData = fetchBinanceKlines("SKHYNIXUSDT", limit);
  var brentData = fetchBinanceKlines("BZUSDT", limit);
  var wtiData = fetchBinanceKlines("CLUSDT", limit);
  var goldData = fetchBinanceKlines("XAUUSDT", limit);
  var silverData = fetchBinanceKlines("XAGUSDT", limit);
  
  var timestamps = Object.keys(skhyDrData).sort();
  if (timestamps.length === 0) return;
  
  var lastRow = sheet.getLastRow();
  var existingTimes = {};
  if (lastRow > 1) {
    var rawTimes = sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues();
    for (var i = 0; i < rawTimes.length; i++) {
      var cellText = rawTimes[i][0] ? rawTimes[i][0].toString().trim() : "";
      if (cellText) existingTimes[cellText] = true;
    }
  }
  
  var newRows = [];
  for (var k = 0; k < timestamps.length; k++) {
    var ts = parseInt(timestamps[k], 10);
    var d = new Date(ts);
    
    var timeStrMin = Utilities.formatDate(d, "Asia/Taipei", "yyyy-MM-dd HH:mm");
    
    if (!existingTimes[timeStrMin]) {
      var skhyDr = skhyDrData[ts];
      var skhyLocal = skhyLocalData[ts];
      var brent = brentData[ts];
      var wti = wtiData[ts];
      var gold = goldData[ts];
      var silver = silverData[ts];
      
      if (skhyDr && skhyLocal && brent && wti && gold && silver) {
        var skhyPrem = parseFloat((((skhyDr / 0.1) / skhyLocal - 1) * 100).toFixed(2));
        var oilSpread = parseFloat((brent - wti).toFixed(2));
        var metalRatio = parseFloat((gold / silver).toFixed(2));
        
        newRows.push([
          timeStrMin, skhyPrem, skhyDr, skhyLocal,
          oilSpread, brent, wti, metalRatio, gold, silver
        ]);
      }
    }
  }
  
  if (newRows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, 10).setValues(newRows);
    Logger.log("🎉 成功自動補齊 " + newRows.length + " 筆數據");
  }
}

function fetchBinanceKlines(symbol, limit) {
  var url = "https://fapi.binance.com/fapi/v1/klines?symbol=" + symbol + "&interval=1m&limit=" + limit;
  try {
    var res = UrlFetchApp.fetch(url, { 
      headers: { "User-Agent": "Mozilla/5.0" },
      muteHttpExceptions: true 
    });
    if (res.getResponseCode() === 200) {
      var json = JSON.parse(res.getContentText());
      var result = {};
      for (var i = 0; i < json.length; i++) {
        result[json[i][0]] = parseFloat(json[i][4]);
      }
      return result;
    }
  } catch (e) {}
  return {};
}