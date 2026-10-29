from power_monitor.services.bank import summarize

def snapshot(stale=False, mixed=False):
    configs=[dict(id='a',name='A',capacity_ah=100,nominal_voltage=51.2),dict(id='b',name='B',capacity_ah=200,nominal_voltage=51.2)]
    statuses=[dict(id='a',state='connected',stale=False),dict(id='b',state='connected',stale=stale)]
    def r(soc,power,temp,source):
        return dict(scope='pack',source=source,soc_percent=soc,power_w=power,temperatures_c=temp,alarms=[],timestamp='2026-01-01T00:00:00+00:00')
    readings={'a':r(50,100,[20,25],'hardware'),'b':r(80,-300,[22,30],'mock' if mixed else 'hardware')}
    readings['b']['alarms']=['cell_undervoltage']
    return configs,statuses,readings

def test_weighted_soc_power_and_alarms():
    result=summarize(*snapshot())
    assert result['soc_percent']==70
    assert result['input_power_w']==100
    assert result['output_power_w']==300
    assert result['net_power_w']==-200
    assert result['reporting_count']==2
    assert result['temperature_min_c']==20
    assert result['temperature_max_c']==30
    assert result['alarms'][0]['battery_id']=='b'
    assert result['complete']

def test_stale_pack_excluded_and_flagged():
    result=summarize(*snapshot(stale=True))
    assert not result['complete']
    assert result['reporting_count']==1
    assert result['net_power_w']==100
    assert not result['power_complete']
    assert not result['alarm_coverage_complete']
    assert result['excluded_battery_ids']==['b']

def test_no_mock_and_real_mix():
    result=summarize(*snapshot(mixed=True))
    assert result['mixed_sources']
    assert result['net_power_w'] is None

def test_empty_bank_and_unknown_scope():
    assert summarize([],[],{})['soc_percent'] is None
    configs,statuses,readings=snapshot()
    readings['b']['scope']='bank'
    result=summarize(configs,statuses,readings)
    assert result['reporting_count']==1
    assert result['net_power_w']==100
