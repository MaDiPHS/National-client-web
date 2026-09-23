/*
 * Copyright (c) 2013-2023 NIBIO.
 *
 * This file is part of VIPSWeb 
 * (see https://gitlab.nibio.no/VIPS/VIPSWeb).
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 */

/**
 * Utility JavaScript. Used here and there. To whom it may concern... 
 *
 * @author Tor-Einar Skog <tor-einar.skog@nibio.no>
 */

/**
 * Builds a parameter string from an array of values
 * @param paramName
 * @param values
 * @returns {String}
 */
function buildPathParamString(paramName, values)
{
	var pathParamString = "";
	for(i in values)
	{
		pathParamString += "&" + paramName + "=" + values[i];
	}
	return pathParamString;
}



/**
 * 
 * @returns the current system time as a Moment.js object
 */
function getSystemTime(){
	if(settings.systemTimeExact != null)
	{
		return systemTime = moment(settings.systemTimeExact);
	}
	return systemTime = moment().add(settings.systemTimeOffsetMonths,"months");
}

function getSystemTimeAsUnixTimeStamp()
{
	return getSystemTime().valueOf();
}

function getStandardFormattedTimestamp(timestamp)
{
	// Using ISO 8601
	return moment(timestamp).format();
}

function getSimpleFormattedTimestamp(timestamp)
{
	return moment(timestamp).format("YYYY-MM-DD HH:mm");
}

function getStandardFormattedDate(timestamp)
{
	return moment(timestamp).format("YYYY-MM-DD");
}

function setMomentToMidnight(momentObj)
{
	return momentObj.hour(0).minute(0).second(0).millisecond(0);
}

function getCurrentYear()
{
	return getSystemTime().year();
	
}

/**
 * Returns the computed CSS display of the element. Handling both IE
 * and the normal browsers
 * @param theElement
 * @returns {String} the computed display value
 */
function getElementComputedDisplay(theElement)
{
	return theElement.currentStyle ? theElement.currentStyle.display :
        getComputedStyle(theElement, null).display;
}

/* Sorting functions used on JSON objects returned from VIPSLogic */

/**
 * Comparing weather stations alphabetically by name
 */
var compareWeatherStations = function(a,b)
{
	return compareStrings(a["name"],b["name"]);
}

/**
 * Comparing preparations alphabetically
 */
var comparePreparations = function(a,b)
{
	return compareStrings(a["preparationName"],b["preparationName"]);
}

var compareStrings = function(a,b)
{
	if(a < b)
	{
		return -1;
	}
	if(a > b)
	{
		return 1;
	}
	return 0;
}

var compareForecastResults = function(a,b)
{
	if(a["validTimeStart"] < b["validTimeStart"])
	{
		return -1;
	}
	if(a["validTimeStart"] > b["validTimeStart"])
	{
		return 1;
	}
	return 0;
}

/**
 * 
 * @returns {Boolean}
 */
function supportsHTML5Storage() {
  try {
    return 'localStorage' in window && window['localStorage'] !== null;
  } catch (e) {
    return false;
  }
}

/**
 * Store  locally on client
 * @param settingsDict key based input.
 */
function storeLocalSettings(settingsDict)
{
	//Test localStorage
	if(!supportsHTML5Storage() || localStorage[""])
	{
		return;
	}
		
	for(var key in settingsDict)
	{
		if(! settingsDict.hasOwnProperty(key))
		{
			continue;
		}
		localStorage[key] = settingsDict[key];
	}
}

/**
 * @param keys array of keys to look for
 * @param allOrNothing if true (default), returns null if not all keys are found in local storage
 * @returns requested Local settings stored at client
 */
function getLocalSettings(keys, allOrNothing)
{
	
	//Test localStorage
	if(!supportsHTML5Storage() || localStorage[""])
	{
		return null;
	}
	
	var allOrNothing = typeof allOrNothing !== 'undefined' ? allOrNothing : true;
	
	var retVal = {};
	for(var i in keys)
	{
		if(localStorage[keys[i]] != null)
		{
			retVal[keys[i]] = localStorage[keys[i]];
		}
	}
	return (allOrNothing && keys.length != Object.keys(retVal).length) ? null : retVal;
}

/**
 * Converts a string like this "6,3,23,1,100" => [6,3,23,1,100]
 * @param csvString
 * @returns {Array}
 */
function getIntArrayFromCsvString(csvString)
{
	//console.log(csvString);
	if(csvString == null || csvString == "")
	{
		return [];
	}
	else
	{
		var retVal = [];
		var tmp = csvString.split(",");
		for(var i in tmp)
		{
			retVal.push(parseInt(tmp[i]));
		}
		return retVal;
	}
}

/**
 * Depends on the value of currentLanguage and defaultLanguage in /currentLanguage.js
 * @param organism
 * @returns {String}
 */
function getLocalizedOrganismName(organism)
{
	// Fallback in case nothing works
	if(organism == null)
	{
		return gettext("Unnamed");
	}
	// Attempting the following languages (in order): current language, default language, English
	var languages = [settings.currentLanguage, settings.defaultLanguage, "en"];
	for(var j in languages)
	{
		for(var i in organism.organismLocaleSet)
		{
			localeSet = organism.organismLocaleSet[i];
			//console.log(localeSet);
			if(localeSet.organismLocalePK.locale === languages[j])
			{
				return localeSet.localName;
			}
		}
	}
	// Then we try the latin name
	if(organism.latinName !== null 
			&& organism.latinName !== "")
	{
		return organism.latinName;
	}
	// Then the trade name
	if(organism.tradeName !== null
			&& organism.tradeName !== "")
	{
		return organism.tradeName;
	}
	// Then we give up
	return gettext("Unnamed");
}

function capitalizeFirstLetter(string) {
    return string && string.charAt(0).toUpperCase() + string.slice(1);
}

var sortMessages = function(a,b)
{
	var momentA = moment(a.datePub);
	var momentB = moment(b.datePub);
	if(momentA.isBefore(momentB))
	{
		return -1;
	}
	if(momentA.isSame(momentB))
	{
		return 0;
	};
	return 1;
}

var sortObservationMessages = function(a,b)
{
	var momentA = moment(a.timeOfObservation);
	var momentB = moment(b.timeOfObservation);
	if(momentA.isBefore(momentB))
	{
		return -1;
	}
	if(momentA.isSame(momentB))
	{
		return 0;
	};
	return 1;
}

var sortOrganisms = function(a,b)
{
	var nameA = getLocalizedOrganismName(a);
	var nameB = getLocalizedOrganismName(b);
	return nameA < nameB ? -1 :
			nameA > nameB ? 1 :
				0;
}

function getMultipleSelectedValues(list)
{
	var retVal = [];
	for(var i=0; i<list.options.length;i++)
	{
		var opt = list.options[i];
		if(opt.selected)
		{
			retVal.push(opt.value);
		}
	}
	return retVal;
}

function getJSON(ambiguousVar)
{
	try
	{
		// Is it a JSON string?
		return JSON.parse(ambiguousVar);
	}
	catch(e)
	{
		return isDict(ambiguousVar) ? ambiguousVar : null; 
	}
}


function isDictEmpty(v){
	return Object.keys(v).length == 0;
}

function isDict(v){
	return typeof v==='object' && v!==null && !(v instanceof Array) && !(v instanceof Date);
}

/**
 * Unfortunately, this method depends on momentjs, since date parsing directly in JavaScript is...hard
 */
function getUnixTimestampFromJSON(ambiguousValue)
{
	var possibleDateObject;
	if(!isMomentJSAvailable())
	{
		possibleDateObject = new Date(ambiguousValue);
		console.info("Warning: Parsing date without MomentJS. Can't guarantee correct result.");
	}
	else
	{
		possibleDateObject = moment(ambiguousValue).toDate();
	}
	if(possibleDateObject.getTime() === NaN && typeof parseInt(ambiguousValue) === "number")
	{
		return parseInt(ambiguousValue);
	}
	else
	{
		return possibleDateObject.getTime();
	}
}

function isMomentJSAvailable()
{
	try {
		moment();
		return true;
	}
	catch (err)
	{
		return false;
	}

}

/**
 * Depends on the value of currentLanguage and languageCode in settings.js
 * @param cropCategory
 * @returns {String}
 */
function getLocalizedCropCategoryName(cropCategory)
{
	// Fallback in case nothing works
	if(cropCategory === null)
	{
		return "Unnamed";
	}
	// Attempting the following languages (in order): current language, default language, English
	var languages = [settings.currentLanguage, settings.languageCode, "en"];
	for(var j in languages)
	{
		for(var i in cropCategory.cropCategoryLocalSet)
		{
			var localeSet = cropCategory.cropCategoryLocalSet[i];
			if(localeSet.cropCategoryLocalPK.locale.trim() == languages[j].trim())
			{
				return localeSet.localName;
			}
		}
	}
	// Then we try the latin name
	if(cropCategory.defaultName !== null 
			&& cropCategory.defaultName !== "")
	{
		return cropCategory.defaultName;
	}
	// Then we give up
	return gettext("Unnamed");
}
