import os
import numpy as np
import pandas as pd

def find_input_file():
    possible_paths = [
        'data/match_data/event_data_sample_Match_events.csv',
        'sport_hackathon/Ice_Hockey_interactive/data/match_data/event_data_sample_Match_events.csv',
        'event_data_sample_Match_events.csv'
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def preprocess_match():
    input_csv = find_input_file()
    if not input_csv:
        raise FileNotFoundError(
            "Could not find 'event_data_sample_Match_events.csv'. "
            "Please ensure it is placed in 'data/match_data/' or the root directory."
        )
    
    # Save processed match inside match_data/processed_match/
    output_dir = 'sport_hackathon/Ice_Hockey_interactive/data/match_data/processed_match'
    output_csv = os.path.join(output_dir, 'processed_match_30fps.csv')
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading match data from {input_csv}...")
    df = pd.read_csv(input_csv)
    
    # Sort chronologically by Period and MatchClock
    df = df.sort_values(by=['Period', 'MatchClock']).reset_index(drop=True)
    
    fps = 30
    dt = 1.0 / fps
    processed_periods = []
    
    coord_cols = [c for c in df.columns if 'Coordinates' in c]
    
    for period, group in df.groupby('Period'):
        min_clock = group['MatchClock'].min()
        max_clock = group['MatchClock'].max()
        
        # Create a uniform 30 FPS timeline for this period
        clock_timeline = np.arange(min_clock, max_clock + dt, dt)
        
        period_df = pd.DataFrame({
            'Period': period,
            'MatchClock': clock_timeline,
            'Frame': np.arange(len(clock_timeline))
        })
        
        group_indexed = group.set_index('MatchClock')
        group_dedup = group_indexed[~group_indexed.index.duplicated(keep='first')].copy()
        
        # Parse coordinate strings ('x,y') into separate X and Y numeric columns
        for col in coord_cols:
            if col in group_dedup.columns:
                valid_coords = group_dedup[col].dropna()
                if not valid_coords.empty:
                    xy = group_dedup[col].str.split(',', expand=True)
                    group_dedup.loc[:, col + '_X'] = pd.to_numeric(xy[0], errors='coerce')
                    group_dedup.loc[:, col + '_Y'] = pd.to_numeric(xy[1], errors='coerce')
                    
        # Identify numeric columns for linear interpolation
        numeric_cols = group_dedup.select_dtypes(include=[np.number]).columns.tolist()
        
        # Reindex to uniform timeline
        reindexed = group_dedup.reindex(group_dedup.index.union(clock_timeline)).sort_index()
        
        # Linearly interpolate ONLY numeric columns
        interpolated_numeric = reindexed[numeric_cols].interpolate(method='linear').loc[clock_timeline]
        for col in numeric_cols:
            if col in interpolated_numeric.columns:
                period_df[col] = interpolated_numeric[col].values
                
        # Forward-fill non-numeric columns (categorical event data, player names, etc.)
        non_numeric_cols = [c for c in group.columns if c not in numeric_cols and c not in coord_cols and c != 'Period']
        for col in non_numeric_cols:
            if col in group_dedup.columns:
                reindexed_non_num = group_dedup[col].reindex(group_dedup.index.union(clock_timeline)).sort_index()
                period_df[col] = reindexed_non_num.ffill().loc[clock_timeline].values
                
        processed_periods.append(period_df)
        
    final_df = pd.concat(processed_periods, ignore_index=True)
    final_df.to_csv(output_csv, index=False)
    print(f"Successfully preprocessed {len(final_df)} frames at {fps} FPS. Saved to {output_csv}")
    return final_df

if __name__ == '__main__':
    preprocess_match()