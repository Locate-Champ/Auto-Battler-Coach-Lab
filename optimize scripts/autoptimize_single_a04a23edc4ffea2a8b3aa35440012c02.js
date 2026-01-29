jQuery(document).ready(function($){if(typeof itemTooltipDataGlobal==='undefined'){console.error('Item tooltip data not found.');return;}
tippy.delegate('body',{target:'.item-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'item-tooltip-theme',onShow(instance){const itemApiName=instance.reference.getAttribute('data-item-apiname');const itemData=itemTooltipDataGlobal[itemApiName];if(itemData){const tooltipContent=generateItemTooltipHTML(itemData);instance.setContent(tooltipContent);}else{instance.setContent('Item data not found.');}},});tippy.delegate('body',{target:'.builder-item-icon',content:'Loading...',allowHTML:true,interactive:false,delay:[800,0],maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'item-tooltip-theme',onShow(instance){if(!instance.reference.isConnected){return false;}
const itemApiName=instance.reference.getAttribute('data-item-apiname');const itemData=itemTooltipDataGlobal[itemApiName];if(itemData){const tooltipContent=generateItemTooltipHTML(itemData);instance.setContent(tooltipContent);}else{instance.setContent('Item data not found.');}},});function generateItemTooltipHTML(data){const headerHTML=`
            <div class="item-tooltip-header">
                <img decoding="async" src="${data.icon_url}" alt="${data.name}">
                <div class="item-tooltip-text">
                    <div class="item-tooltip-title">${data.name}</div>
                    <div class="item-tooltip-info">
                        ${generateItemInfoHTML(data.variables)}
                    </div>
                </div>
            </div>
        `;const descriptionHTML=`
            <div class="item-tooltip-description">
                ${parseItemDescription(data.desc_parsed)}
            </div>
        `;let recipeHTML='';if(data.recipe&&data.recipe.length>0){const recipeComponents=data.recipe.map(component=>`
                <img decoding="async" src="${component.icon_url}" alt="${component.name}">
            `).join('<span>+</span>');recipeHTML=`
                <div class="divider04"></div>
                <div class="item-tooltip-recipe">
                    ${recipeComponents}
                </div>
            `;}
const compositions=getCompositionsForItem(data.apiName);let compositionsHTML='';if(compositions.length>0){compositionsHTML=`
                <div class="divider04"></div>
                <div class="condition-tooltip-comps">
                    ${generateCompositionsByTierHTML(compositions)}
                </div>
            `;}
return`
            <div class="item-tooltip-container">
                ${headerHTML}
                <div class="divider04"></div>
                ${descriptionHTML}
                ${recipeHTML}
                ${compositionsHTML}
            </div>
        `;}
function parseItemDescription(desc){if(!desc)return'';const iconsWithSvg=['scaleAP','scaleMana','scaleAD','scaleAS','scaleDA','scaleDR','scaleArmor','scaleMR','scaleSV','scaleHealth','scaleCrit','scaleCritMult','scaleRange','goldCoins'];desc=desc.replace(/%i:([^%]+)%/g,(match,iconName)=>{const iconBaseName=iconName;const iconUrlSvg=`/wp-content/uploads/tooltip/icons/${iconBaseName}.svg`;const iconUrlPng=`/wp-content/uploads/tooltip/icons/${iconBaseName}.png`;const hasSvg=iconsWithSvg.includes(iconBaseName);const iconUrl=hasSvg?iconUrlSvg:iconUrlPng;return`<img src="${iconUrl}" alt="${iconName} Icon" class="icon-inline">`;});desc=desc.replace(/<([^>]+)>(.*?)<\/\1>/g,(match,tagName,innerText)=>{if(tagName==='br'||tagName==='li'){return`<${tagName}>${innerText}</${tagName}>`;}else{return`<span class="${tagName}">${innerText}</span>`;}});return desc;}
function generateItemInfoHTML(variables){const variableIcons={'Health':{baseName:'scaleHealth',hasSvg:true},'Mana':{baseName:'scaleMana',hasSvg:true},'ManaRegen':{baseName:'TFTManaRegen',hasSvg:false},'AD':{baseName:'scaleAD',hasSvg:true},'AP':{baseName:'scaleAP',hasSvg:true},'StatOmnivamp':{baseName:'scaleSV',hasSvg:true},'Armor':{baseName:'scaleArmor',hasSvg:true},'MagicResist':{baseName:'scaleMR',hasSvg:true},'AS':{baseName:'scaleAS',hasSvg:true},'CritChance':{baseName:'scaleCrit',hasSvg:true},'DA':{baseName:'scaleDA',hasSvg:true},'DR':{baseName:'scaleDR',hasSvg:false},};const variableAliases={'DA':['DA','{1543aa48}'],'DR':['DR','{cd951938}'],};const orderedVariables=['Health','Mana','ManaRegen','AD','AP','Armor','MagicResist','AS','StatOmnivamp','CritChance','DA','DR'];let infoHTML='';for(let varName of orderedVariables){let displayName=varName;let varValue;if(variables.hasOwnProperty(varName)){varValue=variables[varName];}else{if(variableAliases.hasOwnProperty(varName)){for(let alias of variableAliases[varName]){if(variables.hasOwnProperty(alias)){varValue=variables[alias];break;}}}}
if(typeof varValue!=='undefined'){let actualValue;if(typeof varValue==='object'&&varValue!==null){actualValue=varValue.value!==null?varValue.value:varValue.string_value;}else{actualValue=varValue;}
if(actualValue===null||actualValue===undefined){continue;}
const iconInfo=variableIcons[displayName];if(iconInfo){let valueToDisplay=actualValue;if(['AS','CritChance'].includes(displayName)){valueToDisplay='+'+valueToDisplay+'%';}else if(['AD','DA','DR','StatOmnivamp'].includes(displayName)){let numericValue=parseFloat(actualValue);numericValue=Math.round(numericValue*100);valueToDisplay='+'+numericValue+'%';}else{valueToDisplay='+'+valueToDisplay;}
let iconUrl;if(iconInfo.hasSvg){iconUrl=`/wp-content/uploads/tooltip/icons/${iconInfo.baseName}.svg`;}else{iconUrl=`/wp-content/uploads/tooltip/icons/${iconInfo.baseName}.png`;}
infoHTML+=`
                        <img src="${iconUrl}" alt="${displayName} Icon"> ${valueToDisplay} 
                    `;}}}
return infoHTML.trim();}
function getCompositionsForItem(itemApiName){if(!window.compositionDataGlobal||!itemApiName){return[];}
const compositions=[];const addedCompositions=new Set();Object.values(window.compositionDataGlobal).forEach(comp=>{let foundInRequired=false;let foundInStrong=false;let strongConditionTierModifier=0;if(comp.required_condition&&comp.required_condition.type==='Items'&&comp.required_condition.data&&comp.required_condition.data.apiName===itemApiName){foundInRequired=true;}
if(comp.strong_conditions&&Array.isArray(comp.strong_conditions)){comp.strong_conditions.forEach(condition=>{if(condition.type==='Items'&&condition.data&&condition.data.apiName===itemApiName){foundInStrong=true;strongConditionTierModifier=condition.tierModifier||0;}});}
const foundInCompositionItems=false;if((foundInRequired||foundInStrong||foundInCompositionItems)&&!addedCompositions.has(comp.ID)){let tierModifier=0;if(foundInStrong){tierModifier=strongConditionTierModifier;}else{tierModifier=0;}
compositions.push({id:comp.ID,name:comp.name,representative_champion:comp.representative_champion,composition_tier:comp.composition_tier,tier_modifier:tierModifier});addedCompositions.add(comp.ID);}});return compositions;}
function generateCompositionsByTierHTML(compositions){const tierOrder={'OP':7,'S+':6,'S':5,'A':4,'B':3,'C':2,'D':1};compositions.sort((a,b)=>{const modifiedTierA=calculateModifiedTier(a.composition_tier,a.tier_modifier);const modifiedTierB=calculateModifiedTier(b.composition_tier,b.tier_modifier);const tierValueA=tierOrder[modifiedTierA]||3;const tierValueB=tierOrder[modifiedTierB]||3;if(tierValueA!==tierValueB){return tierValueB-tierValueA;}
return a.name.localeCompare(b.name);});const limitedCompositions=compositions.slice(0,10);return limitedCompositions.map(comp=>generateCompositionItemHTML(comp)).join('');}
function calculateModifiedTier(baseTier,tierModifier){const tierValues={'D':1,'C':2,'B':3,'A':4,'S':5,'S+':6,'OP':7};const tierNames={1:'D',2:'C',3:'B',4:'A',5:'S',6:'S+',7:'OP'};const baseValue=tierValues[baseTier]||3;const modifiedValue=Math.min(7,Math.max(1,baseValue+tierModifier));return tierNames[modifiedValue];}
function generateCompositionItemHTML(comp){const compUrl=`${window.location.origin}/?p=${comp.id}`;let championImg='';let championApiname='';if(comp.representative_champion&&window.championDataGlobal&&window.championDataGlobal[comp.representative_champion]){const champion=window.championDataGlobal[comp.representative_champion];championImg=champion.tileIcon_url||champion.icon_url;championApiname=comp.representative_champion;}
const modifiedTier=calculateModifiedTier(comp.composition_tier,comp.tier_modifier);const tierClass='flow-image-sTier';let html=`<a rel="noopener noreferrer" class="tooltip-comp-link no-lightbox" href="${compUrl}">`;if(championImg){html+=`<img data-champion-apiname="${championApiname}" alt="${comp.name}" src="${championImg}" class="champion-icon ${tierClass}" decoding="async">`;}
html+=`<span class="tier-label"><span class="tier-dropdown-label" data-value="${modifiedTier}">${modifiedTier}</span></span>`;html+=`<div class="comp-name">${comp.name}</div>`;html+='</a>';return html;}});