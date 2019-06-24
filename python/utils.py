import numpy as np
import pandas as pd
import pytz
from pathlib import Path
Path.ls = lambda x: list(x.iterdir())
from collections import OrderedDict
import matplotlib.pyplot as plt
import pvlib

def plot_compare(data, res, reference):
    res_month = monthly(res)/1000
    effective_irradiance = get_pvlib_eirrad(data)
    eii = group_monthly(effective_irradiance)/1000
    eii = reindex_monthly_fr(eii)
    fig, axes = plt.subplots(2,1,sharex=True,figsize=(12,12));

    pd.concat([res_month.qinc_front, reference['Irradiance Mean Front'], eii], axis=1,sort=False).plot.bar(ax=axes[0]);
    axes[0].set_title('Front')

    pd.concat([res_month.qinc_back_low, reference['Irradiance Mean Rear']], axis=1,sort=False).plot.bar(ax=axes[1]);
    axes[1].set_title('Back')
    return

def plot_gain(s1, s2, resample='monthly'):
    if resample=='monthly':
        s1 = monthly(s1)/1000
        s2 = monthly(s2)/1000
    
    
    fig, ax = plt.subplots(figsize=(12,5))
    (pd.concat([s1, s2], axis=1,sort=False)
    .plot.bar(ax=ax, stacked=True, color=['blue', 'violet']));
    ax.set_title('Gain')
    gain = 100*(s2/s1)
    add_value_labels(ax, gain, spacing=5)
    return

def ifnone(a,b):
    "`a` if `a` is not None, otherwise `b`."
    return b if a is None else a

def add_value_labels(ax, labels=None, spacing=5):
    """Add labels to the end of each bar in a bar chart.

    Arguments:
        ax (matplotlib.axes.Axes): The matplotlib object containing the axes
            of the plot to annotate.
        spacing (int): The distance between the labels and the bars.
    """
    
    # For each bar: Place a label
    labels = ifnone(labels, [None]*len(ax.patches))
    for rect, label in zip(ax.patches, labels):
        # Get X and Y placement of label from rect.
        y_value = rect.get_height()
        x_value = rect.get_x() + rect.get_width() / 2

        # Number of points between bar and label. Change to your liking.
        space = spacing
        # Vertical alignment for positive values
        va = 'bottom'

        # If value of bar is negative: Place label below bar
        if y_value < 0:
            # Invert space to place label below
            space *= -1
            # Vertically align label at top
            va = 'top'

        # Use Y value as label and format number with one decimal place
        label = "{:.1f}".format(ifnone(label, y_value))

        # Create annotation
        ax.annotate(
            label,                      # Use `label` as label
            (x_value, y_value),         # Place label at end of the bar
            xytext=(0, space),          # Vertically shift label by `space`
            textcoords="offset points", # Interpret `xytext` as offset in points
            ha='center',                # Horizontally center label
            va=va)                      # Vertically align label differently for
                                        # positive and negative values.
    return

            
def group_monthly(df, year=2018):
    return (df.groupby([lambda x: x.year, lambda x: x.month]).sum()).loc[year,:]
    
def reindex_monthly_fr(data):
    index=['Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
                                  'Juillet', 'Août','Septembre', 'Octobre', 'Novembre', 'Décembre']
    if isinstance(data, pd.DataFrame):
        return pd.DataFrame(data.values, index=index, columns=data.columns )
    if isinstance(data, pd.Series):
        return pd.Series(data.values, index=index, name=data.name)

def monthly(data, year=2018):
    return reindex_monthly_fr(group_monthly(data, year))



def report_flo(data, res):
    bf_gain = (100*res['qinc_back_high']+res['qinc_back_low'])/(2*res['qinc_front'])
    bf_gain.name = 'bf_gain'
    results = pd.concat([data[['ghi', 'dhi']], 
                         res[['qinc_front', 'qinc_back_high', 'qinc_back_low']],
                         bf_gain
                        ], axis=1)
    return reindex_monthly_fr(group_monthly(results)/1000)


def get_pvlib_eirrad(data):
    sandia_module = pvlib.pvsystem.retrieve_sam(name='SandiaMod').Canadian_Solar_CS5P_220M___2009_

    airmass = pvlib.atmosphere.get_relative_airmass(data.zenith)
    aoi = pvlib.irradiance.aoi(data.surface_tilt, data.surface_azimuth, data.zenith, data.azimuth)
    dni_extra = pvlib.irradiance.get_extra_radiation(data.index)
    dni_extra = pd.Series(dni_extra, index=data.index)
    poa_sky_diffuse = pvlib.irradiance.haydavies(data.surface_tilt, data.surface_azimuth,
                                                 data['dhi'], data['dni'], dni_extra,
                                                 data.zenith, data.azimuth)
    poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(data.surface_tilt, data.ghi, albedo=data.albedo)
    poa_irrad = pvlib.irradiance.poa_components(aoi, data.dni, poa_sky_diffuse, poa_ground_diffuse)
    effective_irradiance = pvlib.pvsystem.sapm_effective_irradiance(poa_irrad.poa_direct, 
                                                                    poa_irrad.poa_diffuse, 
                                                                    airmass, 
                                                                    aoi, 
                                                                    sandia_module,
                                                                    reference_irradiance=1)
    effective_irradiance.name = 'Irradiance NREL'
    return effective_irradiance

# def my_report(report, pvarray):

#     # Initialize the report
#     if report is None:
#         list_keys = ['qinc_front', 'qinc_back_high', 'qinc_back_low', 'iso_front', 'iso_back']
#         report = OrderedDict({key: [] for key in list_keys})
#     # Add elements to the report
#     if pvarray is not None:
#         pvrow = pvarray.pvrows[0]  # use center pvrow
#         report['qinc_front'].append(
#             pvrow.front.get_param_weighted('qinc'))
#         report['qinc_back_high'].append(
#             get_irradiance_module(pvrow))
#         report['qinc_back_low'].append(
#             get_irradiance_module(pvrow, 'low'))
#         report['iso_front'].append(
#             pvrow.front.get_param_weighted('isotropic'))
#         report['iso_back'].append(
#             pvrow.back.get_param_weighted('isotropic'))
#     else:
#         # No calculation was performed, because sun was down
#         report['qinc_front'].append(np.nan)
#         report['qinc_back_high'].append(np.nan)
#         report['qinc_back_low'].append(np.nan)
#         report['iso_front'].append(np.nan)
#         report['iso_back'].append(np.nan)

#     return report

class MyReportBuilder(object):
    """A class is required to build reports when running calculations with
    multiprocessing because of python constraints"""

    @staticmethod
    def build(report, pvarray):
        # Initialize the report as a dictionary
        if report is None:
            list_keys = ['qinc_front', 'qinc_back_high', 'qinc_back_low', 'iso_front', 'iso_back']
            report = {key: [] for key in list_keys}
        # Add elements to the report
        def _get_irradiance_module(pvrow, module='high', param='qinc', reduc=np.mean):
            if module=='high':
                module_index = [0,1,2]
            else:
                module_index = [3,4,5]
            res = []
            for i in module_index:
                res.append(pvrow.back.all_surfaces[i].params[param])
            if reduc is None:
                return np.array(res)
            else:
                return reduc(np.array(res))

        if pvarray is not None:
            row = int(len(pvarray.pvrows)/2)
            pvrow = pvarray.pvrows[row]  # use center pvrow
            report['qinc_front'].append(
                pvrow.front.get_param_weighted('qinc'))
            report['qinc_back_high'].append(
                _get_irradiance_module(pvrow))
            report['qinc_back_low'].append(
                _get_irradiance_module(pvrow, 'low'))
            report['iso_front'].append(
                pvrow.front.get_param_weighted('isotropic'))
            report['iso_back'].append(
                pvrow.back.get_param_weighted('isotropic'))
        else:
            # No calculation was performed, because sun was down
            report['qinc_front'].append(np.nan)
            report['qinc_back_high'].append(np.nan)
            report['qinc_back_low'].append(np.nan)
            report['iso_front'].append(np.nan)
            report['iso_back'].append(np.nan)
        return report

    @staticmethod
    def merge(reports):
        """Works for dictionary reports"""
        report = reports[0]
        # Merge only if more than 1 report
        if len(reports) > 1:
            keys_report = list(reports[0].keys())
            for other_report in reports[1:]:
                for key in keys_report:
                    report[key] += other_report[key]
        return report


def read_tmy(filename, columns=None, coerce_year=None):
    if columns is None:
        columns = ['ghi', 'dni', 'dhi','temp_air', 'temp_dew', 
                   'humidity', 'air_pressure','wind_speed', 'wind_dir', 'snow']
        

    with open(filename, 'r') as csvdata:

        # read in file metadata, advance buffer to second line
        firstline = csvdata.readline().rstrip('\n').split(",")
        secondline = csvdata.readline().rstrip('\n').split(",")
        meta = dict(zip(firstline,secondline))
        meta['Latitude'] = float(meta['Latitude'])
        meta['Longitude'] = float(meta['Longitude'])
        meta['Elevation'] = float(meta['Elevation'])
        meta['Time Zone'] = int(meta['Time Zone'])
        fixed_tz = pytz.FixedOffset(float(meta['Time Zone']) * 60)

        def _parsedate(ymdh, year=None):
            "parser to get a coerced year from a tmy file"
            ymdh = pd.datetime.strptime(ymdh, '%Y %m %d %H %M')
            if year is not None:
                ymdh = ymdh.replace(year=year)
            return ymdh
        
        data = pd.read_csv(csvdata, header=0, 
                           index_col='datetime', 
                           parse_dates={'datetime': [0,1,2,3,4]}, 
                           date_parser=lambda x: _parsedate(x, year=coerce_year)
                          )
        data.columns = columns
        return meta, data.tz_localize(fixed_tz)

import dateutil
def read_pvgis(filename, coerce_year=2018):
    "Reads a pvgis file"
    with open(filename, 'r') as csvdata:
        # read in file metadata, advance buffer to second line
        gps_data = {}
        for i in range(3):
            line = csvdata.readline()
            attribute = line.rstrip('\n').split(" ")
            gps_data[attribute[0][0:-1]] = float(attribute[1])

        months_year = pd.read_csv(csvdata, nrows=12, engine='python')
    
        def _parsedate(ymdh, year=None):
            "parser to get a coerced year from a tmy file"

            date = dateutil.parser.parse(ymdh, dayfirst=True)
            if year is not None:
                date = date.replace(year=year)
            return date

        date_col = 'datetime'
        data = pd.read_csv(csvdata, 
                           header=0,
                           names=['datetime',
                                  'temp_air','humidity','ghi', 
                                   'dni', 'dhi',
                                   'infrared_downwars', 
                                   'wind_speed', 'wind_dir','air_pressure'],
                           parse_dates=True,
                           date_parser=lambda x: _parsedate(x, year=coerce_year),
                           index_col=date_col)
        return gps_data, months_year, data


