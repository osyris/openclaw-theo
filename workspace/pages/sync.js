(function() {
  'use strict';

  // --- LZ-String-like compression (simple UTF16 variant) ---
  // Minimal LZString compressToEncodedURIComponent / decompressFromEncodedURIComponent
  var LZ = (function(){
    var f = String.fromCharCode;
    var keyStr = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$";
    var baseReverseDic = {};
    for (var i = 0; i < keyStr.length; i++) baseReverseDic[keyStr.charAt(i)] = i;

    function compressToUint8Array(input) {
      if (input == null) return new Uint8Array(0);
      var res = _compress(input, 6, function(a){return keyStr.charAt(a);});
      return new TextEncoder().encode(res);
    }

    function compress(input) {
      if (input == null) return "";
      return _compress(input, 6, function(a){return keyStr.charAt(a);});
    }

    function decompress(input) {
      if (input == null || input === "") return null;
      input = input.replace(/ /g, "+");
      return _decompress(input.length, 32, function(index){return baseReverseDic[input.charAt(index)];});
    }

    function _compress(uncompressed, bitsPerChar, getCharFromInt) {
      var i, value, ii, context_dictionary = {}, context_dictionaryToCreate = {},
        context_c = "", context_wc = "", context_w = "",
        context_enlargeIn = 2, context_dictSize = 3, context_numBits = 2,
        context_data = [], context_data_val = 0, context_data_position = 0;

      for (ii = 0; ii < uncompressed.length; ii++) {
        context_c = uncompressed.charAt(ii);
        if (!Object.prototype.hasOwnProperty.call(context_dictionary, context_c)) {
          context_dictionary[context_c] = context_dictSize++;
          context_dictionaryToCreate[context_c] = true;
        }
        context_wc = context_w + context_c;
        if (Object.prototype.hasOwnProperty.call(context_dictionary, context_wc)) {
          context_w = context_wc;
        } else {
          if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
            if (context_w.charCodeAt(0) < 256) {
              for (i = 0; i < context_numBits; i++) {
                context_data_val = (context_data_val << 1);
                if (context_data_position == bitsPerChar - 1) {
                  context_data_position = 0;
                  context_data.push(getCharFromInt(context_data_val));
                  context_data_val = 0;
                } else { context_data_position++; }
              }
              value = context_w.charCodeAt(0);
              for (i = 0; i < 8; i++) {
                context_data_val = (context_data_val << 1) | (value & 1);
                if (context_data_position == bitsPerChar - 1) {
                  context_data_position = 0;
                  context_data.push(getCharFromInt(context_data_val));
                  context_data_val = 0;
                } else { context_data_position++; }
                value = value >> 1;
              }
            } else {
              value = 1;
              for (i = 0; i < context_numBits; i++) {
                context_data_val = (context_data_val << 1) | value;
                if (context_data_position == bitsPerChar - 1) {
                  context_data_position = 0;
                  context_data.push(getCharFromInt(context_data_val));
                  context_data_val = 0;
                } else { context_data_position++; }
                value = 0;
              }
              value = context_w.charCodeAt(0);
              for (i = 0; i < 16; i++) {
                context_data_val = (context_data_val << 1) | (value & 1);
                if (context_data_position == bitsPerChar - 1) {
                  context_data_position = 0;
                  context_data.push(getCharFromInt(context_data_val));
                  context_data_val = 0;
                } else { context_data_position++; }
                value = value >> 1;
              }
            }
            context_enlargeIn--;
            if (context_enlargeIn == 0) {
              context_enlargeIn = Math.pow(2, context_numBits);
              context_numBits++;
            }
            delete context_dictionaryToCreate[context_w];
          } else {
            value = context_dictionary[context_w];
            for (i = 0; i < context_numBits; i++) {
              context_data_val = (context_data_val << 1) | (value & 1);
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else { context_data_position++; }
              value = value >> 1;
            }
          }
          context_enlargeIn--;
          if (context_enlargeIn == 0) {
            context_enlargeIn = Math.pow(2, context_numBits);
            context_numBits++;
          }
          context_dictionary[context_wc] = context_dictSize++;
          context_w = String(context_c);
        }
      }
      if (context_w !== "") {
        if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
          if (context_w.charCodeAt(0) < 256) {
            for (i = 0; i < context_numBits; i++) {
              context_data_val = (context_data_val << 1);
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else { context_data_position++; }
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 8; i++) {
              context_data_val = (context_data_val << 1) | (value & 1);
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else { context_data_position++; }
              value = value >> 1;
            }
          } else {
            value = 1;
            for (i = 0; i < context_numBits; i++) {
              context_data_val = (context_data_val << 1) | value;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else { context_data_position++; }
              value = 0;
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 16; i++) {
              context_data_val = (context_data_val << 1) | (value & 1);
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else { context_data_position++; }
              value = value >> 1;
            }
          }
          context_enlargeIn--;
          if (context_enlargeIn == 0) {
            context_enlargeIn = Math.pow(2, context_numBits);
            context_numBits++;
          }
          delete context_dictionaryToCreate[context_w];
        } else {
          value = context_dictionary[context_w];
          for (i = 0; i < context_numBits; i++) {
            context_data_val = (context_data_val << 1) | (value & 1);
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else { context_data_position++; }
            value = value >> 1;
          }
        }
        context_enlargeIn--;
        if (context_enlargeIn == 0) {
          context_enlargeIn = Math.pow(2, context_numBits);
          context_numBits++;
        }
      }
      // Mark the end
      value = 2;
      for (i = 0; i < context_numBits; i++) {
        context_data_val = (context_data_val << 1) | (value & 1);
        if (context_data_position == bitsPerChar - 1) {
          context_data_position = 0;
          context_data.push(getCharFromInt(context_data_val));
          context_data_val = 0;
        } else { context_data_position++; }
        value = value >> 1;
      }
      while (true) {
        context_data_val = (context_data_val << 1);
        if (context_data_position == bitsPerChar - 1) {
          context_data.push(getCharFromInt(context_data_val));
          break;
        } else context_data_position++;
      }
      return context_data.join('');
    }

    function _decompress(length, resetValue, getNextValue) {
      var dictionary = [], enlargeIn = 4, dictSize = 4, numBits = 3,
        entry = "", result = [], i, w, c, bits, resb, maxpower, power,
        data = {val: getNextValue(0), position: resetValue, index: 1};

      for (i = 0; i < 3; i++) dictionary[i] = i;

      bits = 0; maxpower = Math.pow(2,2); power = 1;
      while (power != maxpower) {
        resb = data.val & data.position;
        data.position >>= 1;
        if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
        bits |= (resb > 0 ? 1 : 0) * power;
        power <<= 1;
      }
      var next = bits;
      switch (next) {
        case 0:
          bits = 0; maxpower = Math.pow(2,8); power = 1;
          while (power != maxpower) {
            resb = data.val & data.position;
            data.position >>= 1;
            if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
            bits |= (resb > 0 ? 1 : 0) * power;
            power <<= 1;
          }
          c = f(bits);
          break;
        case 1:
          bits = 0; maxpower = Math.pow(2,16); power = 1;
          while (power != maxpower) {
            resb = data.val & data.position;
            data.position >>= 1;
            if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
            bits |= (resb > 0 ? 1 : 0) * power;
            power <<= 1;
          }
          c = f(bits);
          break;
        case 2: return "";
      }
      dictionary[3] = c;
      w = c;
      result.push(c);
      while (true) {
        if (data.index > length) return "";
        bits = 0; maxpower = Math.pow(2, numBits); power = 1;
        while (power != maxpower) {
          resb = data.val & data.position;
          data.position >>= 1;
          if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
          bits |= (resb > 0 ? 1 : 0) * power;
          power <<= 1;
        }
        switch (c = bits) {
          case 0:
            bits = 0; maxpower = Math.pow(2,8); power = 1;
            while (power != maxpower) {
              resb = data.val & data.position;
              data.position >>= 1;
              if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
              bits |= (resb > 0 ? 1 : 0) * power;
              power <<= 1;
            }
            dictionary[dictSize++] = f(bits);
            c = dictSize - 1;
            enlargeIn--;
            break;
          case 1:
            bits = 0; maxpower = Math.pow(2,16); power = 1;
            while (power != maxpower) {
              resb = data.val & data.position;
              data.position >>= 1;
              if (data.position == 0) { data.position = resetValue; data.val = getNextValue(data.index++); }
              bits |= (resb > 0 ? 1 : 0) * power;
              power <<= 1;
            }
            dictionary[dictSize++] = f(bits);
            c = dictSize - 1;
            enlargeIn--;
            break;
          case 2: return result.join('');
        }
        if (enlargeIn == 0) { enlargeIn = Math.pow(2, numBits); numBits++; }
        if (dictionary[c]) { entry = dictionary[c]; }
        else { if (c === dictSize) { entry = w + w.charAt(0); } else { return null; } }
        result.push(entry);
        dictionary[dictSize++] = w + entry.charAt(0);
        enlargeIn--;
        if (enlargeIn == 0) { enlargeIn = Math.pow(2, numBits); numBits++; }
        w = entry;
      }
    }

    return { compress: compress, decompress: decompress };
  })();

  // --- Toast ---
  function showToast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:60px;left:50%;transform:translateX(-50%);' +
      'background:rgba(30,30,30,0.92);color:#fff;padding:10px 22px;border-radius:12px;' +
      'font-size:15px;z-index:99999;pointer-events:none;opacity:0;transition:opacity .3s;' +
      'font-family:-apple-system,BlinkMacSystemFont,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.3);';
    document.body.appendChild(t);
    requestAnimationFrame(function(){ t.style.opacity = '1'; });
    setTimeout(function(){ t.style.opacity = '0'; setTimeout(function(){ t.remove(); }, 400); }, 2000);
  }

  // --- Import on load ---
  var params = new URLSearchParams(window.location.search);
  var syncData = params.get('sync');
  if (syncData) {
    try {
      var json = LZ.decompress(syncData);
      var data = JSON.parse(json);
      Object.keys(data).forEach(function(k) {
        localStorage.setItem(k, data[k]);
      });
      params.delete('sync');
      var newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '') + window.location.hash;
      window.history.replaceState(null, '', newUrl);
      // Show toast then reload
      showToast('Данные синхронизированы! 🎉');
      setTimeout(function(){ window.location.reload(); }, 1500);
    } catch(e) {
      console.error('Sync import failed:', e);
      showToast('Ошибка синхронизации ❌');
    }
    return; // Don't add the button if we're importing
  }

  // --- Sync button ---
  var btn = document.createElement('button');
  btn.textContent = '🔄';
  btn.title = 'Синхронизировать данные';
  btn.style.cssText = 'position:fixed;bottom:16px;left:16px;z-index:9999;width:36px;height:36px;' +
    'border-radius:50%;border:none;background:rgba(255,255,255,0.75);backdrop-filter:blur(8px);' +
    'font-size:18px;cursor:pointer;box-shadow:0 1px 6px rgba(0,0,0,.15);opacity:0.5;' +
    'transition:opacity .2s,transform .2s;display:flex;align-items:center;justify-content:center;' +
    'padding:0;line-height:1;-webkit-tap-highlight-color:transparent;';
  btn.addEventListener('mouseenter', function(){ btn.style.opacity = '1'; btn.style.transform = 'scale(1.1)'; });
  btn.addEventListener('mouseleave', function(){ btn.style.opacity = '0.5'; btn.style.transform = 'scale(1)'; });

  btn.addEventListener('click', function() {
    var data = {};
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      data[k] = localStorage.getItem(k);
    }
    var json = JSON.stringify(data);
    var compressed = LZ.compress(json);
    var url = window.location.origin + window.location.pathname + '?sync=' + compressed;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function() {
        showToast('Ссылка скопирована!');
      }, function() {
        fallbackCopy(url);
      });
    } else {
      fallbackCopy(url);
    }
  });

  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showToast('Ссылка скопирована!'); }
    catch(e) { showToast('Не удалось скопировать ❌'); }
    ta.remove();
  }

  document.body.appendChild(btn);
})();
