import pandas as pd
import pvlib
from timezonefinder import TimezoneFinder
from datetime import timedelta

def get_solar_position(latitude, longitude, timezone, start_date, end_date, freq="15min"):
    """
    Calcula a posição do sol para um intervalo de tempo, garantindo que
    um dia inteiro seja coberto mesmo que as datas de início e fim sejam iguais.
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # CORREÇÃO: Garante que o intervalo cubra o dia inteiro
    # Adiciona um dia ao final e usa 'inclusive="left"' para não incluir a meia-noite do dia seguinte.
    end_dt_exclusive = end_dt + timedelta(days=1)

    times = pd.date_range(start=start_dt, end=end_dt_exclusive, freq=freq, tz=timezone, inclusive="left")
    
    if times.empty:
        return pd.DataFrame()

    location = pvlib.location.Location(latitude, longitude, tz=timezone)
    solar_position = location.get_solarposition(times)
    
    # Retorna apenas os momentos em que o sol está acima do horizonte
    return solar_position[solar_position['apparent_elevation'] > 0]

def get_sun_events(latitude, longitude, timezone, date):
    """
    Calcula o nascer, o pôr do sol e o meio-dia solar para uma data.
    """
    location = pvlib.location.Location(latitude, longitude, tz=timezone)
    sun_events = location.get_sun_rise_set_transit(pd.to_datetime(date))
    return {
        'sunrise': sun_events['sunrise'].iloc[0],
        'sunset': sun_events['sunset'].iloc[0],
        'noon': sun_events['transit'].iloc[0]
    }