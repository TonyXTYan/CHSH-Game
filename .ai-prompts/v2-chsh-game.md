major codebase change 
review and help me find out what's the best strategy if I want to:

player sees they are A or B (upon one teammate disconnect, the remaining player should stay as their original A/B )

A player only sees question AB
B player only sees question XY

add two new metric
* the success rate is computed as 
- if (B,Y) combination is asked, team need to respond with one True and one False
- for all other combinations, players need to respond with both True or both False
* the score is the average of 
- +1 for good response
- -1 for bad response
hide metric about trace avg, balance, balanced trace, CHSH Value

I want this change to be backwards compatiable to the current game too, and if any future versions, perhaps use a toggle in dashboard to switch mode?
 
the participant's page probably don't have to change much, 

make sure when running either version, the irrelavent code components are deactivated. 

review the codebase, then output your plan in a markdown file

thank you so much