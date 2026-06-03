#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define NOMBRE_BALIZA "Baliza Inf-Izquierda"

#define ServicioBateria BLEUUID((uint16_t)0x180F)

BLECharacteristic CaracteristicasNivelBateria(
  BLEUUID((uint16_t)0x2A19),
  BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
);
BLEDescriptor DescriptorNivelBateria(BLEUUID((uint16_t)0x2901));

class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    Serial.println("Cliente conectado");
  }
  void onDisconnect(BLEServer* pServer) {
    Serial.println("Cliente desconectado");
  }
};

uint8_t nivel = 75;

void setup() {
  Serial.begin(115200);
  Serial.printf("Iniciando baliza: %s\n", NOMBRE_BALIZA);

  // Aumentar potencia de emisión al máximo
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_DEFAULT, ESP_PWR_LVL_P9);
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV,     ESP_PWR_LVL_P9);

  BLEDevice::init(NOMBRE_BALIZA);

  BLEServer *Servidor = BLEDevice::createServer();
  Servidor->setCallbacks(new MyServerCallbacks());

  BLEService *Bateria = Servidor->createService(ServicioBateria);
  Bateria->addCharacteristic(&CaracteristicasNivelBateria);
  DescriptorNivelBateria.setValue("Baliza BLE IoT Master");
  CaracteristicasNivelBateria.addDescriptor(&DescriptorNivelBateria);
  CaracteristicasNivelBateria.addDescriptor(new BLE2902());

  Servidor->getAdvertising()->addServiceUUID(ServicioBateria);
  Bateria->start();
  Servidor->getAdvertising()->start();

  Serial.println("Baliza activa y emitiendo...");
}

void loop() {
  CaracteristicasNivelBateria.setValue(&nivel, 1);
  CaracteristicasNivelBateria.notify();
  delay(1000);
}
