#include <WiFi.h>
#include "LabGateway.h"

const char* WIFI_SSID = "REDE";
const char* WIFI_PASSWORD = "SENHA";
const char* LAB_URL = "https://SEU-ENDERECO-NGROK";
const char* LAB_TOKEN = "TOKEN_FORNECIDO_PELO_PROFESSOR";

LabGatewayClient lab(LAB_URL, LAB_TOKEN, "grupo_01", "Estacao 01", "Grupo 01");

unsigned long ultimoEnvio = 0;
const unsigned long INTERVALO_MS = 30000;

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
}

void loop() {
  if (millis() - ultimoEnvio >= INTERVALO_MS) {
    ultimoEnvio = millis();

    float temperatura = 24.7;
    float umidade = 61.2;

    String dados = "{\"temperatura\":" + String(temperatura, 2) +
                   ",\"umidade\":" + String(umidade, 2) + "}";
    String unidades = "{\"temperatura\":\"C\",\"umidade\":\"%\"}";

    bool ok = lab.send(dados, unidades);
    Serial.println(ok ? "LabGateway: enviado" : "LabGateway: falha");
  }
}
