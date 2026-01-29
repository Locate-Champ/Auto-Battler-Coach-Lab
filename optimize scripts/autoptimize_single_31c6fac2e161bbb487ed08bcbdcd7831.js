jQuery(document).ready(function($){if(typeof traitTooltipDataGlobal==='undefined'){console.error('Trait tooltip data not found.');return;}
const isTouchDevice='ontouchstart'in window||navigator.maxTouchPoints>0;tippy.delegate('body',{target:'.trait-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'trait-tooltip-theme',touch:isTouchDevice?true:false,trigger:isTouchDevice?'click':'mouseenter focus',hideOnClick:isTouchDevice?true:true,onShow(instance){const traitApiName=instance.reference.getAttribute('data-trait-apiname');const traitData=traitTooltipDataGlobal[traitApiName];if(traitData){const tooltipContent=generateTraitTooltipHTML(traitData);instance.setContent(tooltipContent);}else{instance.setContent('Trait data not found.');}},});function generateTraitTooltipHTML(data){const headerHTML=`
            <div class="trait-header">
                <img src="${data.icon_url}" alt="${data.name}">
                <div class="trait-name">${data.name}</div>
            </div>
        `;const descriptionHTML=`
            <div class="trait-description">
                ${parseTraitDescription(data.desc_parsed)}
            </div>
        `;let championsHTML='';if(data.champions&&data.champions.length>0){const sortedChampions=data.champions.slice().sort((a,b)=>{const aHasUnlock=hasUnlockConditions(a.apiName);const bHasUnlock=hasUnlockConditions(b.apiName);if(aHasUnlock!==bHasUnlock){return aHasUnlock?1:-1;}
const costA=getChampionCost(a.apiName);const costB=getChampionCost(b.apiName);if(costA!==costB){return costA-costB;}
return a.name.localeCompare(b.name);});championsHTML='<div class="trait-champion-list">';sortedChampions.forEach(champion=>{const cost=getChampionCost(champion.apiName);const hasUnlock=hasUnlockConditions(champion.apiName);if(hasUnlock){championsHTML+=`<div class="trait-champion-container">`;championsHTML+=`<img src="${champion.icon_url}" alt="${champion.name}" class="champion-icon trait-champion-list-icon trait-champion-list-icon--cost${cost}" data-champion-apiName="${champion.apiName}" />`;championsHTML+=`<img src="/wp-content/uploads/tooltip/icons/unlockIcon.svg" alt="Unlockable" class="trait-unlock-icon" />`;championsHTML+=`</div>`;}else{championsHTML+=`<img src="${champion.icon_url}" alt="${champion.name}" class="champion-icon trait-champion-list-icon trait-champion-list-icon--cost${cost}" data-champion-apiName="${champion.apiName}" />`;}});championsHTML+='</div>';}
return`
            <div class="trait-tooltip">
                ${headerHTML}
                ${descriptionHTML}
                ${championsHTML}
            </div>
        `;}
function parseTraitDescription(desc){if(!desc)return'';desc=desc.replace(/%i:([^%]+)%/g,(match,iconName)=>{const iconBaseName=iconName;const iconUrlSvg=`/wp-content/uploads/tooltip/icons/${iconBaseName}.svg`;const iconUrlPng=`/wp-content/uploads/tooltip/icons/${iconBaseName}.png`;const iconsWithSvg=['scaleAP','scaleMana','scaleAD','scaleAS','scaleDA','scaleArmor','scaleMR','scaleSV','scaleHealth','scaleCrit','scaleCritMult','goldCoins','hp','mana'];const hasSvg=iconsWithSvg.includes(iconBaseName);const iconUrl=hasSvg?iconUrlSvg:iconUrlPng;return`<img src="${iconUrl}" alt="${iconName} Icon" class="icon-inline">`;});desc=desc.replace(/<row>(.*?)<\/row>/g,(match,innerText)=>{return`${innerText}`;});desc=desc.replace(/<\/?expandRow>/g,'');desc=desc.replace(/<([^>]+)>(.*?)<\/\1>/g,(match,tagName,innerText)=>{if(tagName==='br'||tagName==='li'){return`<${tagName}>${innerText}</${tagName}>`;}else{return`<span class="${tagName}">${innerText}</span>`;}});return desc;}
function getChampionCost(apiName){if(typeof championDataGlobal!=='undefined'&&championDataGlobal[apiName]&&typeof championDataGlobal[apiName].cost!=='undefined'){return championDataGlobal[apiName].cost;}
return 6;}
function hasUnlockConditions(apiName){if(typeof championDataGlobal!=='undefined'&&championDataGlobal[apiName]){return championDataGlobal[apiName].unlock_conditions!==null&&championDataGlobal[apiName].unlock_conditions!==undefined;}
return false;}});