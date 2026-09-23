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

// TODO: Handle most/all EPSG codes 
proj4.defs(
    'EPSG:25833',
    '+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs'
);

let layers = [];

//let mapserverURL=settings.WMS_SERVER_URL
let modelId = undefined;
let today = getSystemTime().format("YYYY-MM-DD");
let todayLayerIndex = undefined;
let timestamps = undefined;
let currentParameter = "WARNING_STATUS";
let parameters = [currentParameter];
let parameterLabels = {"WARNING_STATUS": "WARNING_STATUS"};
let WMSLayersDateBucket = {};
let map = undefined;
let popup = undefined;



/**
 * Handles moving forwards/backwards in time for the current layer type (Warning status, day degrees etc)
 * @param {Integer} dayIndex the index in the time array (0 = first day in time series)
 */
async function switchLayer(dayIndex)
{
    currentTimestamp = timestamps[dayIndex];
    currentLayer = WMSLayersDateBucket[currentTimestamp][currentParameter];
    // The ordering property was added when we added all layers to the layers list (see initSlidingMap())
    currentLayerOrdering = currentLayer["ordering"];
    for(let i=0;i<layers.length;i++)
    {
        layers[i].setVisible(i==currentLayerOrdering);
        if(layers[i].getVisible())
        {
            // See if there is a language specific legend available
            if(currentLayer.Abstract != undefined && currentLayer.Abstract.trim() != "")
            {
                document.getElementById("layerLegend").innerHTML= getLegendHTML(currentLayer.Abstract);
            }
            else // Fallback to auto generated legend
            {
                document.getElementById("layerLegend").innerHTML='<img id="layerLegendImg" src="' + currentLayer.Style[0].LegendURL[0].OnlineResource + '"/>';
            }
        }
    }
    setCurrentDate(dayIndex);
}


/**
 * Build Legend HTML from Json data, for example:
 {
  "isWarningStatus": true,
  "legendItems": [
    {
      "classification": 0,
      "legendLabel": "Flight period ended",
      "legendIconCSS": "display: inline-block; background-color: #707070;"
    },
    {
      "classification": 2,
      "legendLabel": "Flight period not started",
      "legendIconCSS": "display: inline-block; background-color: #00B457;"
    },
    {
      "classification": 3,
      "legendLabel": "Flight period starting",
      "legendIconCSS": "display: inline-block; background-color: #FFCC00;"
    },
    {
      "classification": 4,
      "legendLabel": "Peak flight activity",
      "legendIconCSS": "display: inline-block; background-color: #FF0000;"
    }
  ]
}
 * @param {String} jsonDataStr (could be other, e.g. HTML)
 * @returns {String} HTML to render as a legend
 */
function getLegendHTML(jsonDataStr)
{
    try
    {
        let jsonData = JSON.parse(jsonDataStr);
        // Using Template literals (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals)
        let legendHTML = `<ul style="list-style: none; padding: 0;">`;
        for(var i=0;i<jsonData.legendItems.length; i++)
        {
            legendHTML += `<li style="margin-bottom: 5px;"><span style="display: inline-block; ${jsonData.legendItems[i].legendIconCSS}">&nbsp;&nbsp;&nbsp;</span> ${jsonData.legendItems[i].legendLabel}</li>`;
        }
        legendHTML += `<ul>`;
        return legendHTML;
    }
    catch(e)
    {
        // Don't know what to do with the string, return as-is
        return jsonDataStr;
    }
}

/**
 * Given the timeseries index, figure out which date it is and display in the time slider
 * @param {Integer} layerIndex
 */
function setCurrentDate(layerIndex)
{
    document.getElementById("currentDate").innerHTML=moment(parseInt(timestamps[layerIndex])).format("YYYY-MM-DD");
}

/**
 *
 * @returns The OpenLayers object for the currently visible layer
 */
function getCurrentVisibleOLLayer()
{
    // The WMS layer returned from mapserver is found
    let currentWMSLayer = WMSLayersDateBucket[currentTimestamp][currentParameter];
    // We have the ordering in the openlayers Map as a property, use that to return the OpenLayers layer
    return layers[currentWMSLayer["ordering"]];
}

/**
 * Used by displayQueryResult() to retrieve values from query templates when user clicks on the map
 *
 * @returns a list of the OpenLayers layers that are available for the current timestamp.
 *
 */
function getLayersForCurrentTimestamp()
{
    layerParams = WMSLayersDateBucket[currentTimestamp];
    paramIdList = Object.keys(layerParams);
    let layersForCurrentTimestamp = [];
    for(let i=0; i< paramIdList.length; i++)
    {
        layersForCurrentTimestamp.push(layers[WMSLayersDateBucket[currentTimestamp][paramIdList[i]]["ordering"]]);
    }
    return layersForCurrentTimestamp;

}

/**
 * Loads map and data, and sets up the initial view of the map
 * @param {*} inputModelId model Id, e.g. PSILARTEMP
 * @param {*} mapAttribution background map source information (displayed in the map)
 */
async function initGridMap(inputModelId, wmsURL, mapAttribution) {
    modelId = inputModelId;
    //debugger;
    var backgroundLayer = new ol.layer.Tile({
		source: new ol.source.OSM({
			//attributions: [
			//	new ol.Attribution({
			//		html: mapAttribution
			//	})
			//]
		})
	});

    //debugger;
    // Get layers from WMS service
    let parser = new ol.format.WMSCapabilities();
    //console.info(mapserverURL + modelId + "?service=WMS&version=1.3.0&request=GetCapabilities");
    let response = await fetch(wmsURL + "?service=WMS&version=1.3.0&request=GetCapabilities&language=" + settings.currentLanguage);
    //let response = await fetch(wmsURL + "?service=WMS&request=GetCapabilities&language={{language.code}}");
    //console.info(wmsURL + "?service=WMS&request=GetCapabilities&language=en");
    //console.info(response.status); // Response is 200 even if a model doesn't exist on the mapserver
    let txt = await response.text();

    //console.info(txt);
    let wmsServiceSuccess = false;
    let isDataReturned = false
    try
    {
        let capabilities = parser.read(txt);
        isDataReturned = capabilities.Capability.Layer != undefined;

        let WMSLayers = isDataReturned ? capabilities.Capability.Layer.Layer : [];

        if(isDataReturned)
        {
            // Test: Are WMSLayers one level behind?
            let testName = WMSLayers[0].Name;
            let testNameParts = testName.split(".");
            // The name must have 3 parts
            // Part 1 of name must equal the model ID
            // Part 3 must be a parseable date (YYYY-MM-DD)
            if(testNameParts.length != 3 || testNameParts[0] != modelId || testNameParts[2].length != 10)
            {
                // This is not the layer we want, we must search one level deeper.
                WMSLayers = WMSLayers[0].Layer;
            }
            //console.info(WMSLayers);
        }
        //console.info(capabilities);
        // Get title and abstract. Could be either at top level or the level below
        let modelTitle = capabilities.Service.Title;
        let modelAbstract = undefined;
        if(modelTitle != undefined && modelTitle.trim() != "")
        {
            modelAbstract = capabilities.Service.Abstract;
        }
        else if(isDataReturned)
        {
            modelTitle = capabilities.Capability.Layer.Layer[0].Title;
            modelAbstract = capabilities.Capability.Layer.Layer[0].Abstract;
        }
        document.getElementById("modelTitle").innerHTML = modelTitle != undefined ? modelTitle : "No name found for model";
        if(modelAbstract != undefined)
        {
            // Placing the sections above/below the map
            let el = new DOMParser().parseFromString(modelAbstract.replaceAll("\n\n",""),"text/html");
            let preamble = el.getElementById("preamble") != null ? el.getElementById("preamble") : el;
            document.getElementById("modelAbstractPreamble").innerHTML = new XMLSerializer().serializeToString(preamble);
            let body = el.getElementById("body") != null ? el.getElementById("body") : null;
            if(body != null)
            {
                document.getElementById("modelAbstractBody").innerHTML = new XMLSerializer().serializeToString(body);
            }
            // Get the parameter explanations
            let props = el.querySelectorAll("[itemprop]");
            for(var i=0;i<props.length;i++)
            {
                parameterLabels[props[i].getAttribute("itemprop")]=props[i].textContent;
            }
        }
        //console.info(capabilities);

        // Analyze and organize layers
        // First dimension: Time
        // Second dimension: Parameter
        for(let i=0;i<WMSLayers.length;i++){
            // Sort by date ascending
            let WMSLayerName = WMSLayers[i].Name;
            let WMSLayerParam = WMSLayerName.split(".")[1];
            // Adding the parameter if it does not exist in the list
            if(parameters.indexOf(WMSLayerParam) < 0)
            {
                parameters.push(WMSLayerParam);
            }
            let timestamp = moment(WMSLayerName.split(".")[2]).valueOf();
            if(WMSLayersDateBucket[timestamp] == undefined)
            {
                WMSLayersDateBucket[timestamp] = {}
            }
            WMSLayersDateBucket[timestamp][WMSLayerParam] = WMSLayers[i];
        }
        //console.info(WMSLayersDateBucket);

        // Iterate timestamps, add all layers chronologically
        timestamps = Object.keys(WMSLayersDateBucket);
        timestamps.sort();
        //console.info(timestamps);

        for(let i=0; i< timestamps.length;i++)
        {
            let dateStr = moment(parseInt(timestamps[i])).format("YYYY-MM-DD");
            if(dateStr == today)
            {
                todayLayerIndex = i;
            }

            // There are normally several parameters per timestamp
            let timestampLayers = WMSLayersDateBucket[timestamps[i]];
            let params = Object.keys(timestampLayers);
            for(let j=0; j<params.length;j++)
            {
                let currentLayer = timestampLayers[params[j]];
                let currentLayerParam = currentLayer.Name.split(".")[1];
                /*if(j==0)
                {
                    console.info(currentLayer.Abstract);
                }*/
                layers.push(
                    new ol.layer.Image({
                        source: new ol.source.ImageWMS({
                            url: wmsURL,
                            params: { "LAYERS": modelId + "." + currentLayerParam + "." + dateStr, "TRANSPARENT": "TRUE" },
                            serverType: "mapserver",
                            ratio: 1,
                            projection: ol.proj.get(currentLayer.CRS[0])
                        }),
                        visible: false,
                        opacity: 0.5
                    })
                );
                // This is the placement in the maps layers collection. By adding it here
                // it's easy to manipulate it
                currentLayer["ordering"] = layers.length -1;
            }
        }

        wmsServiceSuccess = true;
    }
    catch(error)
    {
        //console.info(error);
        //console.info("No data or error from WMS");
    }


    //console.info(WMSLayersDateBucket);

	// Creating the map
	map = new ol.Map({
		target: "mapContainer",
		layers: [backgroundLayer].concat(layers),
		renderer: 'canvas'
	});

    lonLat = [33.82, -13.91];
    zoomLevel = 6;

	// Setting zoom and center for the map (need to do this after creating map. so that we can transform our
	// center to correct map projection)
	var view = new ol.View({
		center: ol.proj.transform(lonLat, 'EPSG:4326', map.getView().getProjection().getCode()),
		zoom: zoomLevel,
		maxMapZoom: 14,
	});
	map.setView(view);

    // If today is outside of the date range, use the most recent timestamp
    if(wmsServiceSuccess && isDataReturned)
    {
        if(todayLayerIndex == undefined)
        {
            todayLayerIndex = timestamps.length -1;
        }

        let range = document.getElementById("layerDateRange");
        range.min = 0;
        range.max = timestamps.length -1;
        range.value = todayLayerIndex;
        setCurrentDate(todayLayerIndex);
        switchLayer(todayLayerIndex);

        // Set zoom and center either based on what the user previously had set,
        // or fit the map to the layer's extent
        var storedMapSettings = getLocalSettings([
            "gridmap.longitude",
            "gridmap.latitude",
            "gridmap.zoomLevel"],
            true);
        if(storedMapSettings != null)
        {
            longitude = parseFloat(storedMapSettings["gridmap.longitude"]);
            latitude = parseFloat(storedMapSettings["gridmap.latitude"]);
            let lonLat=[longitude,latitude];
            zoomLevel = parseInt(storedMapSettings["gridmap.zoomLevel"]);
            map.getView().setCenter(ol.proj.transform(lonLat, 'EPSG:4326', map.getView().getProjection().getCode()));
            map.getView().setZoom(zoomLevel);
        }
        else
        {
            // Zoom and center the map to fit to the extent of the WMS layer.
            // If the current WMS layer has a lot of no-data / invisible values surrounding the
            // visible values, the zoom might appear to be a bit too far out
            let currentWMSLayer = WMSLayersDateBucket[currentTimestamp][currentParameter]
            let WMSExtent = currentWMSLayer.EX_GeographicBoundingBox;
            let extent = ol.proj.transformExtent(WMSExtent, getCurrentVisibleOLLayer().getSource().getProjection().getCode(), map.getView().getProjection());
            map.getView().fit(extent, map.getSize());
        }

        popup = new ol.Overlay({
        element: document.getElementById('popup')
        });
        map.addOverlay(popup);

        map.on('singleclick', displayQueryResult);

        // Store user's zoom/pan preferences for the next browser session
        map.on('moveend', function(evt) {
            // Store map settings
            var centerCoordinate = ol.proj.transform(map.getView().getCenter(), map.getView().getProjection().getCode(),'EPSG:4326');
            var settings = {
                "gridmap.longitude": centerCoordinate[0],
                "gridmap.latitude": centerCoordinate[1],
                "gridmap.zoomLevel": map.getView().getZoom()
            };
            storeLocalSettings(settings);
            });

        // Add the parameter selector
        let radioHTML = "";
        for(let i=0;i<parameters.length;i++)
        {
            radioHTML += '<div class="radio"><label><input type="radio" name="parameter" value="' + parameters[i] + '"' + (parameters[i] == currentParameter ? "checked" : "") + ' onclick="switchParameter(this.value);"/>' + (parameterLabels[parameters[i]] != undefined ? capitalizeFirstLetter(parameterLabels[parameters[i]]) : parameters[i]) + '</label></div>';
        }

        document.getElementById("paramselector").innerHTML = radioHTML;
    }
    else{
        map.getView().setCenter(ol.proj.transform([0,0], 'EPSG:4326', map.getView().getProjection().getCode()));
        map.getView().setZoom(2);
        document.getElementById("paramselector").style.display="none";
        document.getElementById("layerLegend").style.display="none";
        document.getElementById("slidecontainer").style.display="none";
        if(! wmsServiceSuccess)
        {
            alert("Got here");
            document.getElementById("errorMessageContainer").innerHTML="ERROR: Response from server was " + txt;
        }
        else // Service OK, but no data (layers)
        {
            document.getElementById("errorMessageContainer").innerHTML=gettext("The risk map contains no data. Could we be out of season? Please read the model description.");
        }
        document.getElementById("errorMessageContainer").style.display="block";
    }

}

function switchParameter(selectedParameter)
{
    currentParameter = selectedParameter;
    switchLayer(document.getElementById("layerDateRange").value);
}

//var myDefaultWhiteList = $.fn.tooltip.Constructor.DEFAULTS.whiteList;
//myDefaultWhiteList.i = ["aria-hidden", "onclick","style"]

async function displayQueryResult(evt)
{
    let popupElement = popup.getElement();
    $(popupElement).popover('destroy');
    
    
    let currentWMSLayer = WMSLayersDateBucket[currentTimestamp][currentParameter];
    let currentWarningStatusLayer = WMSLayersDateBucket[currentTimestamp]["WARNING_STATUS"];

    // Need to get all layers for today, and combine results from querying all layers
    let layersForCurrentTimestamp = getLayersForCurrentTimestamp();
    let warningStatus = null;
    let parameters = {};
    for(let i=0;i<layersForCurrentTimestamp.length;i++)
    {
        let currentLayer = layersForCurrentTimestamp[i];
        let coordinate = proj4(map.getView().getProjection().getCode(), currentLayer.getSource().getProjection().getCode(), evt.coordinate)
        const url = currentLayer.getSource().getGetFeatureInfoUrl(
            coordinate,
            map.getView().getResolution(),
            currentWMSLayer.CRS[0],
            { 'INFO_FORMAT': 'text/xml' }
        );

        let response = await fetch(url);
        let responseXML = await response.text();
        //console.info(responseXML);
        // User clicked outside of layer extent
        if(responseXML.trim().length == 0)
        {
            continue;
        }
        const parser = new DOMParser();
        const xmlDOM = parser.parseFromString(responseXML,"text/xml");
        const result = xmlDOM.getElementsByTagName("vipsResult")[0]
        if(result) {
            // We may or may not have warning status included
            warningStatus = warningStatus == null ? (xmlDOM.getElementsByTagName("warningStatus").length == 1 ? xmlDOM.getElementsByTagName("warningStatus")[0].getAttribute("value") : null) : warningStatus;
            // User clicked on invisible/invalid part of the layer
            if(warningStatus == -1)
            {
                continue;
            }

            let parameterElements = xmlDOM.getElementsByTagName("parameter");
            for(let i=0;i<parameterElements.length;i++)
            {
                parameters[parameterElements[i].getAttribute("name")] = parameterElements[i].getAttribute("value");
            }
        }
    }

    // User clicked outside of layers contents
    if(warningStatus == null)
    {
        return;
    }

    let paramHTML = "<ul>";
    paramCodes = Object.keys(parameters);
    for(let i=0;i<paramCodes.length;i++)
    {
        paramHTML += "<li>" + (parameterLabels[paramCodes[i]] != undefined ? capitalizeFirstLetter(parameterLabels[paramCodes[i]]) + " (" + paramCodes[i] + ")" : paramCodes[i]) + " = " + parameters[paramCodes[i]] + "</li>"
    }
    paramHTML += "</ul>";

    // Render results
    popup.setPosition(evt.coordinate);
    let wgs84Coordinate = proj4(map.getView().getProjection().getCode(), "EPSG:4326", evt.coordinate)
    $(popupElement).popover({
        'placement': 'top',
        'animation': false,
        'html': true,
        'title': gettext("Map location") + ` [${wgs84Coordinate[1].toFixed(4)}, ${wgs84Coordinate[0].toFixed(4)}] <i class="fa fa-times" style="display: inline-block; cursor: pointer; position: absolute; right: 10px;" aria-hidden="true"  onclick="$(popup.getElement()).popover('destroy');"></i>`,
        'content': '<h4>' + getWarningStatusTitle(currentWarningStatusLayer.Abstract, warningStatus) + '</h4>' + paramHTML
        });
        $(popupElement).popover('show');

}

function getWarningStatusTitle(jsonDataStr, warningStatus)
{
    try
    {
        let jsonData = JSON.parse(jsonDataStr);
        for(let i=0; i<jsonData.legendItems.length; i++)
        {
            let legendItem = jsonData.legendItems[i];
            if(legendItem.classification == warningStatus)
            {
                return legendItem.legendLabel;
            }
        }
        return gettext("Could not determine warning status");
    }
    catch(e)
    {
        return warningStatus == 0 ? gettext("No forecast available")
        : warningStatus == 1 ? gettext("Missing data")
        : warningStatus == 2 ? gettext("No risk of infection")
        : warningStatus == 3 ? gettext("Medium risk of infection")
        : warningStatus == 4 ? gettext("High risk of infection") : "";
    }
}

/**
 * Programmatically move the slider back and forth
 * Used by the arrow buttons (onclick event) on each side of the slider
 * @param {Integer} step 
 */
function moveDateSlider(step)
{
    let slider=document.getElementById("layerDateRange");
    let min = parseInt(slider.min); 
    let max = parseInt(slider.max);
    let newValue = parseInt(slider.value) + step;
    newValue = newValue > max ? max : newValue < min ? min : newValue;
    slider.value=newValue;
    slider.onchange();
}