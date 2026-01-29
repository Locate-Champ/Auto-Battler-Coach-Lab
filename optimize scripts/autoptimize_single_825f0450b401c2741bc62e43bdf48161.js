jQuery(document).ready(function($){if(typeof customConditionTooltipGlobal==='undefined'){console.error('Custom condition tooltip data not found.');return;}
tippy.delegate('body',{target:'.custom-condition-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'augment-tooltip-theme',onShow(instance){const customConditionId=instance.reference.getAttribute('data-custom-condition-id');const customConditionData=customConditionTooltipGlobal.find(condition=>condition.ID==customConditionId);if(customConditionData){let linkedEntity=null;const linkedEntityType=instance.reference.getAttribute('data-linked-entity-type');const linkedEntityApiName=instance.reference.getAttribute('data-linked-entity-apiname');const linkedEntityId=instance.reference.getAttribute('data-linked-entity-id');if(linkedEntityType){linkedEntity={type:linkedEntityType};if(linkedEntityApiName){linkedEntity.apiName=linkedEntityApiName;switch(linkedEntityType){case'Champion':if(typeof window.championDataGlobal!=='undefined'&&window.championDataGlobal[linkedEntityApiName]){const championData=window.championDataGlobal[linkedEntityApiName];linkedEntity.name=championData.name;linkedEntity.cost=championData.cost;}
break;case'Item':if(typeof window.itemTooltipDataGlobal!=='undefined'&&window.itemTooltipDataGlobal[linkedEntityApiName]){linkedEntity.name=window.itemTooltipDataGlobal[linkedEntityApiName].name;}
break;case'Trait':if(typeof window.traitTooltipDataGlobal!=='undefined'&&window.traitTooltipDataGlobal[linkedEntityApiName]){linkedEntity.name=window.traitTooltipDataGlobal[linkedEntityApiName].name;}
break;case'Augment':if(typeof window.augmentTooltipDataGlobal!=='undefined'&&window.augmentTooltipDataGlobal[linkedEntityApiName]){linkedEntity.name=window.augmentTooltipDataGlobal[linkedEntityApiName].name;}
break;}}
if(linkedEntityId){linkedEntity.id=linkedEntityId;if(linkedEntityType==='Opener'&&typeof window.openerDataGlobal!=='undefined'){Object.values(window.openerDataGlobal).forEach(setOpeners=>{if(setOpeners&&typeof setOpeners==='object'){Object.values(setOpeners).forEach(opener=>{if(opener&&(opener.ID==linkedEntityId||opener.id==linkedEntityId)){linkedEntity.name=opener.opener_name||opener.name;}});}});}else if(linkedEntityType==='Composition'&&typeof window.compositionDataGlobal!=='undefined'){const compositionData=window.compositionDataGlobal[linkedEntityId];if(compositionData&&compositionData.name){linkedEntity.name=compositionData.name;}}}}
const tooltipContent=generateCustomConditionTooltipHTML(customConditionData,linkedEntity);instance.setContent(tooltipContent);}else{instance.setContent('Custom condition data not found.');}},});function generateCustomConditionTooltipHTML(data,linkedEntity=null){let displayName=data.name;let displayDescription=data.description;if(linkedEntity&&data.linked_entity_type){const entityName=linkedEntity.name||'';const entityType=data.linked_entity_type.toLowerCase();displayName=displayName.replace(new RegExp(`\\{${entityType}\\}`,'gi'),entityName);displayDescription=displayDescription.replace(new RegExp(`\\{${entityType}\\}`,'gi'),entityName);}
let imageHTML;if(linkedEntity&&data.linked_entity_type){if(data.linked_entity_parent){const linkedEntityIconUrl=getLinkedEntityIconUrlForTooltip(linkedEntity);const costClass=linkedEntity.type==='Champion'&&linkedEntity.cost?`cost${Math.min(Math.max(linkedEntity.cost, 1), 6)}`:'';imageHTML=`
                    <div class="custom-condition-image">
                        <img decoding="async" class="linked-${linkedEntity.type.toLowerCase()}-icon ${costClass}" src="${linkedEntityIconUrl}" alt="${linkedEntity.name}">
                        <div class="alt-info-container"><img decoding="async" src="${data.image}" class="alt-items-icon"></div>
                    </div>
                `;}else{const linkedEntityIconUrl=getLinkedEntityIconUrlForTooltip(linkedEntity);const costClass=linkedEntity.type==='Champion'&&linkedEntity.cost?`cost${Math.min(Math.max(linkedEntity.cost, 1), 6)}`:'';imageHTML=`
                    <div class="custom-condition-image">
                        <img decoding="async" src="${data.image}" alt="${displayName}">
                        <div class="alt-info-container"><img decoding="async" src="${linkedEntityIconUrl}" class="alt-items-icon ${costClass}"></div>
                    </div>
                `;}}else{imageHTML=`
                <div class="custom-condition-image">
                    <img decoding="async" src="${data.image}" alt="${displayName}">
                </div>
            `;}
const titleHTML=`
            <div class="augment-title">
                ${displayName}
            </div>
        `;const dividerHTML=`
            <div class="divider07"></div>
        `;const compositions=getCompositionsForCustomCondition(data.ID);let descriptionHTML=`
            <div class="augment-description">
                ${parseCustomConditionDescription(displayDescription)}
        `;if(compositions.length>0){descriptionHTML+=`
                <div class="divider04"></div>
                <div class="condition-tooltip-comps">
                    ${generateCompositionsByTierHTML(compositions)}
                </div>
            `;}
descriptionHTML+='</div>';return`
            <div class="augment-tooltip">
                ${imageHTML}
                ${titleHTML}
                ${dividerHTML}
                ${descriptionHTML}
            </div>
        `;}
function getOpenerIconUrlForTooltip(linkedEntity){if(!linkedEntity||!linkedEntity.id){return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
if(typeof window.openerDataGlobal!=='undefined'){let openerData=null;Object.values(window.openerDataGlobal).forEach(setOpeners=>{if(setOpeners&&typeof setOpeners==='object'){Object.values(setOpeners).forEach(opener=>{if(opener&&(opener.ID==linkedEntity.id||opener.id==linkedEntity.id)){openerData=opener;}});}});if(openerData){const championList=openerData.champion_list||openerData.champions||[];if(championList.length===0){return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
let bestChampion=null;let bestChampionData=null;if(openerData.representative_champion&&openerData.representative_champion.trim()!==''){const repChampionData=window.championDataGlobal[openerData.representative_champion];if(repChampionData){bestChampionData=repChampionData;}}
if(!bestChampionData){for(const champion of championList){const apiName=champion.champion_api_name||champion.apiName||champion;const championData=window.championDataGlobal[apiName];if(championData){if(!bestChampionData||championData.cost<bestChampionData.cost||(championData.cost===bestChampionData.cost&&apiName<bestChampion)){bestChampion=apiName;bestChampionData=championData;}}}}
if(bestChampionData&&bestChampionData.tileIcon_url){return bestChampionData.tileIcon_url;}}}
return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
function getCompositionIconUrlForTooltip(linkedEntity){if(!linkedEntity||!linkedEntity.id){return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
if(typeof window.compositionDataGlobal!=='undefined'){const compositionData=window.compositionDataGlobal[linkedEntity.id];if(compositionData&&compositionData.representative_champion){if(typeof window.championDataGlobal!=='undefined'){const championData=window.championDataGlobal[compositionData.representative_champion];if(championData&&championData.tileIcon_url){return championData.tileIcon_url;}}}}
return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
function getLinkedEntityIconUrlForTooltip(linkedEntity){if(!linkedEntity)return'/wp-content/uploads/tooltip/icons/questionMark.svg';switch(linkedEntity.type){case'Champion':if(typeof window.championDataGlobal!=='undefined'&&window.championDataGlobal[linkedEntity.apiName]){return window.championDataGlobal[linkedEntity.apiName].tileIcon_url;}
break;case'Item':if(typeof window.itemTooltipDataGlobal!=='undefined'&&window.itemTooltipDataGlobal[linkedEntity.apiName]){return window.itemTooltipDataGlobal[linkedEntity.apiName].icon_url;}
break;case'Trait':if(typeof window.traitTooltipDataGlobal!=='undefined'&&window.traitTooltipDataGlobal[linkedEntity.apiName]){return window.traitTooltipDataGlobal[linkedEntity.apiName].icon_url;}
break;case'Augment':if(typeof window.augmentTooltipDataGlobal!=='undefined'&&window.augmentTooltipDataGlobal[linkedEntity.apiName]){return window.augmentTooltipDataGlobal[linkedEntity.apiName].icon_url;}
break;case'Opener':return getOpenerIconUrlForTooltip(linkedEntity);case'Composition':return getCompositionIconUrlForTooltip(linkedEntity);default:return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
return'/wp-content/uploads/tooltip/icons/questionMark.svg';}
function parseCustomConditionDescription(desc){if(!desc)return'';const iconsWithSvg=['scaleAP','scaleMana','scaleAD','scaleAS','scaleDA','scaleDR','scaleArmor','scaleMR','scaleSV','scaleHealth','scaleCrit','goldCoins'];desc=desc.replace(/%i:([^%]+)%/g,(match,iconName)=>{const iconBaseName=iconName;const iconUrlSvg=`/wp-content/uploads/tooltip/icons/${iconBaseName}.svg`;const iconUrlPng=`/wp-content/uploads/tooltip/icons/${iconBaseName}.png`;const hasSvg=iconsWithSvg.includes(iconBaseName);const iconUrl=hasSvg?iconUrlSvg:iconUrlPng;return`<img src="${iconUrl}" alt="${iconName} Icon" class="icon-inline">`;});desc=desc.replace(/<([^>]+)>(.*?)<\/\1>/g,(match,tagName,innerText)=>{if(tagName==='br'||tagName==='li'){return`<${tagName}>${innerText}</${tagName}>`;}else{return`<span class="${tagName}">${innerText}</span>`;}});return desc;}
function getCompositionsForCustomCondition(customConditionId){if(!window.compositionDataGlobal||!customConditionId){return[];}
const compositions=[];const addedCompositions=new Set();Object.values(window.compositionDataGlobal).forEach(comp=>{let foundInRequired=false;let foundInStrong=false;let strongConditionTierModifier=0;if(comp.required_condition&&comp.required_condition.type==='Custom'&&comp.required_condition.data&&comp.required_condition.data.ID===parseInt(customConditionId)){foundInRequired=true;}
if(comp.strong_conditions&&Array.isArray(comp.strong_conditions)){comp.strong_conditions.forEach(condition=>{if(condition.type==='Custom'&&condition.data&&condition.data.ID===parseInt(customConditionId)){foundInStrong=true;strongConditionTierModifier=condition.tierModifier||0;}});}
if((foundInRequired||foundInStrong)&&!addedCompositions.has(comp.ID)){let tierModifier=0;if(foundInStrong){tierModifier=strongConditionTierModifier;}else{tierModifier=0;}
compositions.push({id:comp.ID,name:comp.name,representative_champion:comp.representative_champion,composition_tier:comp.composition_tier,tier_modifier:tierModifier});addedCompositions.add(comp.ID);}});return compositions;}
function generateCompositionsByTierHTML(compositions){const tierOrder={'OP':7,'S+':6,'S':5,'A':4,'B':3,'C':2,'D':1};compositions.sort((a,b)=>{const modifiedTierA=calculateModifiedTier(a.composition_tier,a.tier_modifier);const modifiedTierB=calculateModifiedTier(b.composition_tier,b.tier_modifier);const tierValueA=tierOrder[modifiedTierA]||3;const tierValueB=tierOrder[modifiedTierB]||3;if(tierValueA!==tierValueB){return tierValueB-tierValueA;}
return a.name.localeCompare(b.name);});const limitedCompositions=compositions.slice(0,10);return limitedCompositions.map(comp=>generateCompositionItemHTML(comp)).join('');}
function calculateModifiedTier(baseTier,tierModifier){const tierValues={'D':1,'C':2,'B':3,'A':4,'S':5,'S+':6,'OP':7};const tierNames={1:'D',2:'C',3:'B',4:'A',5:'S',6:'S+',7:'OP'};const baseValue=tierValues[baseTier]||3;const modifiedValue=Math.min(7,Math.max(1,baseValue+tierModifier));return tierNames[modifiedValue];}
function generateCompositionItemHTML(comp){const compUrl=`${window.location.origin}/?p=${comp.id}`;let championImg='';let championApiname='';if(comp.representative_champion&&window.championDataGlobal&&window.championDataGlobal[comp.representative_champion]){const champion=window.championDataGlobal[comp.representative_champion];championImg=champion.tileIcon_url||champion.icon_url;championApiname=comp.representative_champion;}
const modifiedTier=calculateModifiedTier(comp.composition_tier,comp.tier_modifier);const tierClass='flow-image-sTier';let html=`<a rel="noopener noreferrer" class="tooltip-comp-link no-lightbox" href="${compUrl}">`;if(championImg){html+=`<img data-champion-apiname="${championApiname}" alt="${comp.name}" src="${championImg}" class="champion-icon ${tierClass}" decoding="async">`;}
html+=`<span class="tier-label"><span class="tier-dropdown-label" data-value="${modifiedTier}">${modifiedTier}</span></span>`;html+=`<div class="comp-name">${comp.name}</div>`;html+='</a>';return html;}});