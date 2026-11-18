#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <math.h>

/*
BLOCO PADRAO DE INTEGRACAO

1. Coloque LabGateway.h na mesma pasta do arquivo .ino.
2. Antes do include, informe o nome do grupo/projeto:

   #define LABGATEWAY_NOME "NOME_DO_GRUPO"

3. Em seguida adicione:
   #include "LabGateway.h"

4. Depois que as variaveis dos sensores forem atualizadas, adicione:

   LabGateway.enviar(
       "Nome da medicao 1", variavel1, "unidade",
       "Nome da medicao 2", variavel2, "unidade"
   );

Exemplo:

   LabGateway.enviar(
       "Temperatura", temperatura, "C",
       "Umidade", umidade, "%",
       "Pressao", pressao, "hPa"
   );

A biblioteca cuida automaticamente de:
- identificacao tecnica unica da ESP32
- nome humano da estacao/grupo
- intervalo entre transmissoes
- montagem do JSON
- envio HTTP/HTTPS
- nomes e unidades enviados ao servidor

Nao e necessario criar outro timer nem outra conexao Wi-Fi.
*/

#ifndef LABGATEWAY_URL
#define LABGATEWAY_URL "https://SEU-ENDERECO-LABGATEWAY"
#endif

#ifndef LABGATEWAY_TOKEN
#define LABGATEWAY_TOKEN "TOKEN_FORNECIDO_PELO_PROFESSOR"
#endif

#ifndef LABGATEWAY_INTERVALO_MS
#define LABGATEWAY_INTERVALO_MS 30000UL
#endif

#ifndef LABGATEWAY_NOME
#define LABGATEWAY_NOME "ESTACAO_SEM_NOME"
#endif

class LabGatewayClass {
  String endpoint;
  String token;
  String station;
  unsigned long ultimaTentativa = 0;
  bool primeiraTentativa = true;

  static String escapeJson(const String &s) {
    String out;
    out.reserve(s.length() + 8);
    for (size_t i = 0; i < s.length(); i++) {
      char c = s[i];
      if (c == '"' || c == '\\') out += '\\';
      if (c == '\n') {
        out += "\\n";
      } else if (c == '\r') {
        out += "\\r";
      } else {
        out += c;
      }
    }
    return out;
  }

  static String numberJson(float value) { return String(value, 6); }
  static String numberJson(double value) { return String(value, 6); }

  template <typename T>
  static String numberJson(T value) { return String(value); }

  static void appendSemantic(
      String &, String &, int &, bool &) {}

  template <typename T, typename... Rest>
  static void appendSemantic(
      String &dataJson,
      String &unitsJson,
      int &count,
      bool &valid,
      const char *name,
      T value,
      const char *unit,
      Rest... rest) {

    if (!name || !unit) {
      valid = false;
      return;
    }

    String metric = String(name);
    String unitText = String(unit);
    metric.trim();
    unitText.trim();

    double numeric = static_cast<double>(value);

    if (!metric.length() ||
        metric.length() > 64 ||
        unitText.length() > 32 ||
        !isfinite(numeric)) {
      valid = false;
      return;
    }

    if (count > 0) {
      dataJson += ",";
      unitsJson += ",";
    }

    String escapedMetric = escapeJson(metric);
    dataJson += "\"" + escapedMetric + "\":";
    dataJson += numberJson(value);

    unitsJson += "\"" + escapedMetric + "\":\"";
    unitsJson += escapeJson(unitText);
    unitsJson += "\"";

    count++;
    appendSemantic(dataJson, unitsJson, count, valid, rest...);
  }

  static void appendValues(String &, int &, bool &) {}

  template <typename T, typename... Rest>
  static void appendValues(
      String &json,
      int &index,
      bool &valid,
      T value,
      Rest... rest) {

    double numeric = static_cast<double>(value);
    if (!isfinite(numeric)) {
      valid = false;
      return;
    }

    index++;
    if (index > 1) json += ",";
    json += "\"variavel_" + String(index) + "\":";
    json += numberJson(value);
    appendValues(json, index, valid, rest...);
  }

  void ensureStation() {
    if (station.length()) return;

    uint64_t chip = ESP.getEfuseMac();
    char id[24];
    snprintf(
        id,
        sizeof(id),
        "esp32_%04X%08X",
        (uint16_t)(chip >> 32),
        (uint32_t)chip
    );
    station = String(id);
  }

  bool intervaloLiberado() {
    unsigned long agora = millis();

    if (!primeiraTentativa &&
        (unsigned long)(agora - ultimaTentativa) < LABGATEWAY_INTERVALO_MS) {
      return false;
    }

    primeiraTentativa = false;
    ultimaTentativa = agora;
    return true;
  }

  bool sendJson(const String &dataJson, const String &unitsJson) {
    if (WiFi.status() != WL_CONNECTED) return false;

    ensureStation();

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    if (!http.begin(client, endpoint)) return false;

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-LabGateway-Token", token);

    String stationName = String(LABGATEWAY_NOME);
    stationName.trim();
    if (!stationName.length()) stationName = station;

    String body = "{\"station\":\"" + escapeJson(station) +
                  "\",\"name\":\"" + escapeJson(stationName) +
                  "\",\"group\":\"\",\"data\":" + dataJson +
                  ",\"units\":" + unitsJson + "}";

    int code = http.POST(body);
    http.end();
    return code >= 200 && code < 300;
  }

public:
  LabGatewayClass() : endpoint(LABGATEWAY_URL), token(LABGATEWAY_TOKEN) {
    if (endpoint.endsWith("/")) endpoint.remove(endpoint.length() - 1);
    endpoint += "/api/v1/measurements";
  }

  template <typename T, typename... Rest>
  bool enviar(
      const char *name,
      T value,
      const char *unit,
      Rest... rest) {

    if (!intervaloLiberado()) return true;

    String data = "{";
    String units = "{";
    int count = 0;
    bool valid = true;

    appendSemantic(
        data,
        units,
        count,
        valid,
        name,
        value,
        unit,
        rest...
    );

    data += "}";
    units += "}";

    if (!valid || count == 0 || count > 32) return false;
    return sendJson(data, units);
  }

  template <typename T, typename... Rest>
  bool enviar(T value, Rest... rest) {
    if (!intervaloLiberado()) return true;

    String data = "{";
    int index = 0;
    bool valid = true;

    appendValues(data, index, valid, value, rest...);
    data += "}";

    if (!valid || index == 0 || index > 32) return false;
    return sendJson(data, "{}");
  }
};

inline LabGatewayClass LabGateway;
