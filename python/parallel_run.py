import argparse, sys
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

# import function to run simulations in parallel
import pvlib
from pvfactors.geometry import OrderedPVArray
from pvfactors.run import run_parallel_engine
from pvfactors.engine import PVEngine
from utils import *
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def debug_pvarray(data, pvarray_parameters, idx=0):
    data_idx = data.iloc[idx]
    params = {'axis_azimuth': pvarray_parameters['axis_azimuth'],
             'gcr': pvarray_parameters['gcr'],
             'n_pvrows': pvarray_parameters['n_pvrows'],
             'pvrow_height': pvarray_parameters['pvrow_height'],
             'pvrow_width': pvarray_parameters['pvrow_width'],
             'solar_azimuth': data_idx['azimuth'],
             'solar_zenith': data_idx['zenith'],
             'surface_azimuth': data_idx['surface_azimuth'],
             'surface_tilt': data_idx['surface_tilt']}

    # Create new PV array
    pvarray_w_direct_shading = OrderedPVArray.from_dict(params)
    # Cast shadows
    pvarray_w_direct_shading.cast_shadows()

    f, ax = plt.subplots(figsize=(10, 3))
    pvarray_w_direct_shading.plot(ax)
    plt.show()
    return pvarray_w_direct_shading



def system_def( albedo=0.4, 
                n_modules_vertically=2, 
                module_size=(1.69,1.01), 
                h_ground=1,
                surface_tilt=38,
                axis_azimuth=0,
                surface_azimuth=180,
                n_pvrows=1,
                tracking=False,
                gcr=0.5
                ):
    #modules:
    w_m, h_m = module_size  #width x height of module

    # phisical
    if not tracking:
        h_center = h_ground + np.sin(2*np.pi*38/360)*h_m
    else:
        h_center = h_ground

    pvarray_parameters = {
        'n_pvrows': n_pvrows,            # number of pv rows
        'pvrow_height': h_center,        # height of pvrows (measured at center / torque tube)
        'pvrow_width': n_modules_vertically * h_m,         # width of pvrows
        'tracking':tracking,
        'axis_azimuth': axis_azimuth,       # azimuth angle of rotation axis
        'surface_tilt': surface_tilt,      # tilt of the pv rows
        'surface_azimuth': surface_azimuth,   # azimuth of the pv rows front surface
        'albedo':albedo,
        'gcr': gcr,               # ground coverage ratio,
        'rho_front_pvrow': 0.075,  # pv row front surface reflectivity
        'rho_back_pvrow': 0.075,    # pv row back surface reflectivity
        'cut':{
            i: {'front': 3,'back': 6} for i in range(n_pvrows) # discretize the front  PV row into 3 segments and back in 5
    }
    }
    return pvarray_parameters

def _merge_data(tmy_data, solpos, pvarray_parameters):
    data = pd.DataFrame(index=tmy_data.index)
    data['ghi'] = tmy_data.ghi
    data['dni'] = tmy_data.dni
    data['dhi'] = tmy_data.dhi
    data['zenith'] = solpos.zenith
    data['azimuth'] = solpos.azimuth
    data['surface_tilt'] = pvarray_parameters['surface_tilt']
    data['surface_azimuth'] = pvarray_parameters['surface_azimuth']
    data['albedo'] =  pvarray_parameters['albedo']

    #doing some patching
    idxs = (data.zenith<90) & (data.ghi<10)
    LOGGER.info(f'Correcting {idxs.sum()} indexes, Total GHI discarded = {data[idxs].ghi.sum()}')
    data.loc[idxs, 'zenith'] = 91.
    return data

def get_data(tmy_file, pvarray_parameters, reader='pvgis'):
    '''tmy_file:: location of tmy file
    pvarray_parameters:: output of system_def
    reader:: Use 'pvgis' for PVGIS tmy file format, use 'tmy' for explorador solar tmy files (SAM)'''
    if reader == 'pvgis':
        gps_data, months_year, tmy_data = read_pvgis(tmy_file, coerce_year=2018)
    else:
        gps_data, tmy_data = read_tmy(tmy_file, coerce_year=2018)

    solpos = (pvlib
             .solarposition
             .get_solarposition(tmy_data.index, 
                                gps_data['Latitude'], 
                                gps_data['Longitude'],
                                gps_data['Elevation'])
             )
    
    data = _merge_data(tmy_data, solpos, pvarray_parameters)
    if pvarray_parameters['tracking']:
        back_track = False
        if pvarray_parameters['n_pvrows']>1:
            back_track = True
        tracking = (pvlib
                    .tracking
                    .singleaxis(apparent_zenith=data.zenith, 
                                apparent_azimuth=data.azimuth, 
                                axis_azimuth=pvarray_parameters['axis_azimuth'], 
                                backtrack=back_track,
                                gcr=pvarray_parameters['gcr'])
                    .fillna(0))
        data.surface_azimuth = tracking.surface_azimuth
        data.surface_tilt = tracking.surface_tilt
    return data

def pv_engine_run(data, pvarray_parameters, parallel=0):
    if parallel>0:
        report = run_parallel_engine(MyReportBuilder, pvarray_parameters, data.index, 
                                data.dni, data.dhi, 
                                data.zenith, data.azimuth, 
                                data.surface_tilt, data.surface_azimuth, 
                                data.albedo, n_processes=6)
    else:
        rb = MyReportBuilder()
        engine = PVEngine(pvarray_parameters)
        engine.fit(data.index, 
                    data.dni, 
                    data.dhi, 
                    data.zenith, 
                    data.azimuth, 
                    data.surface_tilt, 
                    data.surface_azimuth,
                    data.albedo
            )
        report = engine.run_all_timesteps(rb.build)

    df_report = pd.DataFrame(report, index=data.index).fillna(0)
    return df_report

if __name__ == '__main__':
    PATH = Path('../data_Comparison_Static-Tracking_for_Kais/Param')
    default_tmy = PATH/'Cadarache.csv'

    parser=argparse.ArgumentParser()
    
    parser.add_argument('--tmy', help='TMY file to use as input', type=str, default=default_tmy)
    parser.add_argument('--jobs', help='number of threds to use', type=int, default=4)


    args=parser.parse_args()
    
    #get args
    n_processes = int(args.jobs)
    tmy_file = args.tmy

    print(f'Args: {n_processes}, {tmy_file}')
    #locate system
    pvarray_parameters = system_def(h_ground=1)
    data = get_data(tmy_file, pvarray_parameters)

 
    # run simulations in parallel mode
    report = run_parallel_engine(MyReportBuilder, pvarray_parameters, data.index, 
                                data.dni, data.dhi, 
                                data.zenith, data.azimuth, 
                                data.surface_tilt, data.surface_azimuth, 
                                data.albedo, n_processes=n_processes)

    # make a dataframe out of the report
    df_report = pd.DataFrame(report, index=data.index).dropna()

    df_report.to_csv('pvfactors_output.csv')