import asyncio
import pytest
from fastapi.testclient import TestClient
from power_monitor.collectors.inverter_solarman import decode, SolarmanInverterCollector
from power_monitor.storage.database import Database
from power_monitor.config import load_config
from power_monitor.api.server import create_app


def inverter_config():
    return dict(id='inverter',name='SunGoldPower',host='192.0.2.1',logger_serial=123,
                expected_serial_prefix='SGP2508150220',interval_seconds=30,max_gap_seconds=90)

def raw():
    pv=[0]*11
    pv[0],pv[8]=2339,2410
    pv[2],pv[10]=500,600
    return dict(identity=[ord(c) for c in 'SGP2508150220-301638'.ljust(20,'\0')],
                battery=[84,529,460],pv=pv,l1=[1528],legs=[731])

def test_decode_and_identity_guard():
    r=decode(inverter_config(),raw()).to_dict()
    assert r['load_total_power_w']==2259
    assert r['pv_total_power_w']==1100
    assert r['pv1_voltage_v']==233.9
    assert r['pv2_voltage_v']==241
    assert 'load_l3_power_w' not in r
    assert r['battery_voltage_v']==52.9
    assert r['inverter_reported_soc_percent']==84
    assert r['inverter_serial']=='SGP2508150220-301638'
    c=inverter_config()
    c['expected_serial_prefix']='OTHER'
    with pytest.raises(ValueError):
        decode(c,raw())
    data=raw()
    data['pv']=[]
    with pytest.raises(ValueError):
        decode(inverter_config(),data)

def test_inverter_persistence(tmp_path):
    path=str(tmp_path/'inverter.db')
    db=Database(path)
    reading=decode(inverter_config(),raw())
    db.save_inverter(reading)
    db.save_inverter(reading)
    db.close()
    db=Database(path)
    assert db.latest_inverter('inverter')['raw_registers']==raw()
    assert len(db.inverter_history('inverter','2000','2100',10))==1
    assert db.latest('inverter') is None
    db.close()

def test_collector_only_approved_reads():
    class Client:
        async def read_holding_registers(self,address,count):
            mapping={0x35:raw()['identity'],0x100:raw()['battery'],0x107:raw()['pv'],
                     0x21b:raw()['l1'],0x232:raw()['legs']}
            assert address in mapping
            assert len(mapping[address])==count
            return mapping[address]
    async def run():
        collector=SolarmanInverterCollector(inverter_config())
        collector.client=Client()
        assert (await collector.read()).to_dict()['load_total_power_w']==2259
    asyncio.run(run())

def test_inverter_api_and_error_recovery(tmp_path,monkeypatch):
    from power_monitor.services import inverter
    class Collector:
        def __init__(self,config): self.config=config
        async def connect(self): pass
        async def read(self): return decode(self.config,raw())
        async def disconnect(self): pass
    monkeypatch.setattr(inverter,'SolarmanInverterCollector',Collector)
    config=load_config('config.mock.yaml')
    config['database']['path']=str(tmp_path/'api.db')
    config['inverter']={**inverter_config(),'enabled':True}
    with TestClient(create_app(config)) as client:
        import time
        for _ in range(30):
            response=client.get('/api/inverter').json()
            if response['reading']: break
            time.sleep(.01)
        assert response['state']=='connected'
        assert not response['stale']
        assert response['reading']['pv_total_power_w']==1100
        assert client.get('/api/inverter/history').json()['readings']
        assert client.get('/api/inverter/history?hours=0').status_code==422

def test_failed_read_does_not_create_telemetry(tmp_path,monkeypatch):
    from power_monitor.services import inverter
    attempted=asyncio.Event()
    class Failed:
        def __init__(self,config): pass
        async def connect(self): raise ConnectionError('unreachable')
        async def disconnect(self): attempted.set()
    monkeypatch.setattr(inverter,'SolarmanInverterCollector',Failed)
    async def run():
        db=Database(str(tmp_path/'failed.db'))
        monitor=inverter.InverterMonitoring(inverter_config(),db)
        monitor.start()
        monitor.start()
        await asyncio.wait_for(attempted.wait(),1)
        assert monitor.status['state']=='disconnected'
        assert db.latest_inverter('inverter') is None
        await monitor.stop()
        db.close()
    asyncio.run(run())
