import pandas as pd
import numpy as np
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA

import pmdarima as pm
# Load the dataset
file_path = 'analysis_data/DALYs_CASES.csv'
print(f"Processing file: {file_path}")
file_name = file_path.split('/')[-1].split('.')[0]
df = pd.read_csv(file_path)
df = df[df['sex_id'] == 3][['year', 'val']].dropna()
df = df.sort_values(by='year')
df = df.set_index('year')
schizophrenia_data = df

# Fit ARIMA model using auto_arima
model_auto = pm.auto_arima(schizophrenia_data,
                           start_p=0, start_q=0,
                           max_p=5, max_q=5,
                           seasonal=False,
                           d=None,  # Auto-difference
                           trace=True,
                           error_action='ignore',
                           suppress_warnings=True,
                           stepwise=True)

print(model_auto.summary())

# Save summary to a .txt file
with open(f'analysis_data/{file_name}_arima_summary.txt', 'w') as f:
    f.write(str(model_auto.summary()))

# Fit the model
model = ARIMA(schizophrenia_data, order=(0,1,1))
model_fit = model.fit()
# Print model summary
print(model_fit.summary())
fitted_values = model_fit.fittedvalues

import matplotlib.pyplot as plt

plt.figure(figsize=(10, 5))
plt.plot(schizophrenia_data[1:], label='Original')
plt.plot(fitted_values[1:], label='Fitted (In-Sample)', color='orange')
plt.title(f'{file_name} In-Sample Fit')
plt.legend()
plt.grid(True)
plt.show()
plt.savefig(f'analysis_data/{file_name}_in_sample_fit.png')
# Forecast to 2050
forecast_years = list(range(2022, 2051))
forecast = model_fit.get_forecast(steps=len(forecast_years))
forecast_values = forecast.predicted_mean
# Combine forecast with original data
forecast_df = pd.DataFrame({'year': forecast_years, 'val': forecast_values})
combined_df = pd.concat([schizophrenia_data.reset_index(), forecast_df], ignore_index=True)
# Plot the results
plt.figure(figsize=(10, 6))
plt.plot(combined_df['year'], combined_df['val'], label='Observed + Forecast')
plt.axvline(x=2021, color='red', linestyle='--', label='Forecast Start')
plt.xlabel('Year')
plt.title(f'ARIMA Forecast for {file_name} to 2050')
plt.legend()
plt.grid()
plt.show()
plt.savefig(f'analysis_data/{file_name}_arima_forecast.png')
