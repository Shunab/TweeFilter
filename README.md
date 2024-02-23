This code if for educational purposes only

This code uses OpenAI API to analyse tweets and publish to discord via webhooks.
Due to new twitter API pricing, this project uses IFTTT to pull tweets to a google sheet and the python script parses through google sheets to analyse tweets.
For reducing token useage, use keyword search to skip relevancy test for obvious content.

Here is an example of the output 
![PHOTO-2023-07-10-14-18-08](https://github.com/Shunab/Tweefilter/assets/115668529/dffed167-032c-4663-9da7-5781f05fedc0)

To get started, make a google service account and paste all the contents in Service_account.json, fill up the config.json file with users (for webhooks) and set up IFTTT applets to send tweets from user to googlesheets
