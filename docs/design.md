# Modes

## Single Stop

Analogous to a clock on one side platform. Shows upcoming trains of all lines in a single direction that stop there. 

1. Get all lines that include stop\_id.  
2. Get upcoming trains for those lines at stop\_id. 

## Single Station

Analogous to standing on a center island platform. Shows all upcoming trains of all lines in both directions that stop there. 

Depending on how the stop ID’s are organized, this may also include stops on other platforms in the same station. 

1. Get all stop ID’s for station.  
2. Get all lines for those stop ID’s.   
3. Get all upcoming trains for those lines. 

## Multi-Station

Novel, convenient mode for use outside a station. Show upcoming arrivals for multiple stations. For example, the stations closest to a home or office. 

1. Get all stop ID’s for stations.   
2. Get all lines for those stop ID’s.   
3. Get all upcoming trains for those lines. 

# Display Logic

Sort and filter upcoming trains. Filter criteria: next n trains and/or trains in next m minutes. 

The top line should display the next train. The bottom line should cycle through trains 2 through n every s seconds. Except, if a second train is also arriving, it should be fixed on the bottom line as well. 

Arriving trains should be displayed until they no longer appear on the upcoming train list. 

# Display Themes

## Dark Theme

As seen in the 28th St 6 station. Black background, white text. Arriving train highlighted in yellow?

## Light Theme

As seen on Union square NRQW platform. Light gray background, black text, arriving trains highlighted in black?

## New Theme

New card based theme. Includes fade in and out animation to scroll through train text and drop out and back animation for bullet.   
