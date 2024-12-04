import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.express as px
import sqlalchemy

# Initialize the app
app = dash.Dash(__name__)
server = app.server
# Connect to SQL Server
engine = sqlalchemy.create_engine(
    r"mssql+pyodbc://sa:ApolloMw8273937$@DESKTOP-FUDH4TF\SQLEXPRESS/c sharp program?driver=ODBC+Driver+17+for+SQL+Server"
)

# Layout with DatePickerRange and Time Inputs
app.layout = html.Div([
    html.H1("Machine Analysis: Uptime, Downtime, and Program Run Count"),
    
    # Date range picker
    dcc.DatePickerRange(
        id='date-picker-range',
        start_date='2024-10-01',  # Default start date
        end_date='2024-10-10',    # Default end date
        display_format='YYYY-MM-DD',
    ),
    
    # Time inputs for time window
    html.Div([
        html.Label("Start Time (HH:MM):"),
        dcc.Input(id='start-time', type='text', value='00:00', placeholder="Start Time (e.g., 08:00)"),
        html.Label("End Time (HH:MM):"),
        dcc.Input(id='end-time', type='text', value='23:59', placeholder="End Time (e.g., 18:00)"),
    ], style={'margin-top': '10px', 'margin-bottom': '10px'}),

    # Graph for uptime/downtime
    dcc.Graph(id='uptime-downtime-graph'),

    # Program run count table
    html.Div(id='program-run-table', style={'margin-top': '20px'}),
])

# Function to fetch data based on selected date range and time window
def fetch_data(start_datetime, end_datetime):
    # SQL query for the selected datetime range
    query = f"""
    SELECT CNCValue, ProgramName, CycleTime, Timestamp
    FROM CNCData
    WHERE Timestamp >= '{start_datetime}' AND Timestamp <= '{end_datetime}'
    ORDER BY Timestamp
    """
    df = pd.read_sql(query, engine)
    return df

# Function to calculate uptime and downtime from the data
def calculate_uptime_downtime(df):
    uptime = 0
    downtime = 0

    for i in range(len(df) - 1):
        current_row = df.iloc[i]
        next_row = df.iloc[i + 1]

        current_timestamp = pd.to_datetime(current_row['Timestamp'])
        next_timestamp = pd.to_datetime(next_row['Timestamp'])

        cnc_value = current_row['CNCValue']
        next_cnc_value = next_row['CNCValue']

        if cnc_value == 0:  # End of a cycle
            uptime += current_row['CycleTime']  # Add cycle time to uptime

        if cnc_value == 0 and next_cnc_value == 1:  # Machine stopped, next start defines downtime
            downtime += (next_timestamp - current_timestamp).total_seconds() / 60  # Downtime in minutes

    return uptime, downtime

# Function to calculate program run counts
def calculate_program_counts(df):
    # Extract program names and dates
    df['ProgramName'] = df['ProgramName'].str.extract(r"//CNC_MEM/USER/JOB/(.+)$")
    df['Date'] = pd.to_datetime(df['Timestamp']).dt.date

    # Count occurrences grouped by ProgramName and Date
    program_counts = df.groupby(['ProgramName', 'Date']).size().unstack(fill_value=0)

    return program_counts

# Callback to update the charts based on date range and time window
@app.callback(
    [Output('uptime-downtime-graph', 'figure'),
     Output('program-run-table', 'children')],
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date'),
     Input('start-time', 'value'),
     Input('end-time', 'value')]
)
def update_charts(start_date, end_date, start_time, end_time):
    # Handle case where start_date and end_date are the same
    if start_date == end_date:
        start_datetime = f"{start_date} {start_time}:00" if start_time else f"{start_date} 00:00:00"
        end_datetime = f"{end_date} {end_time}:00" if end_time else f"{end_date} 23:59:59"
    else:
        start_datetime = f"{start_date} {start_time}:00" if start_time else f"{start_date} 00:00:00"
        end_datetime = f"{end_date} {end_time}:00" if end_time else f"{end_date} 23:59:59"

    # Fetch data for the selected range and time window
    df = fetch_data(start_datetime, end_datetime)

    # Calculate uptime and downtime
    uptime, downtime = calculate_uptime_downtime(df)
    total_time = uptime + downtime
    uptime_percentage = (uptime / total_time) * 100 if total_time > 0 else 0
    downtime_percentage = 100 - uptime_percentage

    # Uptime/Downtime chart
    uptime_downtime_fig = px.bar(
        x=['Uptime', 'Downtime'],
        y=[uptime, downtime],
        labels={'x': 'Status', 'y': 'Minutes'},
        title=f"Uptime/Downtime from {start_date} to {end_date} ({start_time or '00:00'} - {end_time or '23:59'})"
    )

    # Program run counts
    program_counts = calculate_program_counts(df)

    # Create table
    program_run_table = html.Table([
        html.Thead([
            html.Tr([html.Th("Program Name")] + [html.Th(str(date)) for date in program_counts.columns])
        ]),
        html.Tbody([
            html.Tr([html.Td(program)] + [html.Td(program_counts.loc[program, date]) for date in program_counts.columns])
            for program in program_counts.index
        ])
    ], style={'width': '100%', 'border': '1px solid black', 'border-collapse': 'collapse'})

    return uptime_downtime_fig, program_run_table

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
