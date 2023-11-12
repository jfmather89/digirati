# Digirati Tech Test

This project uses spacy and associated model `en_cor_web_sm` to provide an API that extracts from a provided url of a text:
* People and their appearance count in the document
* the associated locations with the people and their association count

## Installation
This project requires python version 3.11. To install the relevant packages run the following command from the root of the project using pip package manager:
```
pip install -r requirements.txt
```

## Running Server
To run the server locally - use the following command in the root folder of the project
```
python -m src.app
```
This will setup a flask development server on 127.0.0.1 on port 5000

## API usage
To use the api send a POST request with the following JSON body to the endpoint `/get-people`
```
{
    "URL": <url of a text file or web page accessible with a GET request>,
    <arbitrary meta dat fields>
}
```
If the request is valid this will provide a JSON response of the following form

```
{
    "URL": <the provided url as above>,
    <arbitrary fields>,
    "people": <a list of json objects of people with name, appearance count and a list of associated with their count >
}
```

An example curl request to this endpoint would be
```
curl -X POST -d '{"URL": "https://www.gutenberg.org/cache/epub/345/pg345.txt", "author": "Bram Stoker", "title": "Dracula"}' http://127.0.0.1:5000/get-people
```

An example response may be
```
{
	"url": "https://www.gutenberg.org/cache/epub/345/pg345.txt",
	"title": "Dracula",
	"author": "Bram Stoker",
	"people": [{
			"name": "Jonathan Harker",
			"count": 8,
			"associated_places": [{
				"name": "Munich",
				"count": 2
			}, {
				"name": "Bucharest",
				"count": 1
			}]
		},
		{
			"name": "Professor Van Helsing",
			"count": 2,
			"associated_places": [{
				"name": "London",
				"count": 1
			}, {
				"name": "Cambridge",
				"count": 1
			}]
		}
	]
}
```