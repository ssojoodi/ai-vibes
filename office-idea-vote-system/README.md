

```
My problem is choosing a lunch spot to order in from for the team on a daily basis. We have a big team and people have favourites to suggest. I want to design a simple web app that grants people a number of points every week and then lets them bid in a reverse Dutch auctions system which lets people suggest their desired lunch place.

Detailed requirements and technical considerations:

use SQLite as a the DB
use a one-file python with minimal overhead but simple, elegant and techy css styling. User another python file for setting up the schema in SQLite if required. But two python files max.
the auction style is a one shot auction, the users point in some portion of their points and highest bidder wins the day
the number of team members is 10, but could become larger in the future
the auction is run everyday until all employees have exhausted their points at which point the number of points is reset to “initial” which is 15 points (as number of employees grows, we’ll apply a multiplier to it for the “initial points” value)
on each day, the auction is finished and winner announced as soon as all employees put in their bids
```