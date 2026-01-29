jQuery(document).ready(function($){if(typeof augmentTooltipDataGlobal==='undefined'){console.error('Augment tooltip data not found.');return;}
tippy.delegate('body',{target:'.augment-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'augment-tooltip-theme',onShow(instance){const augmentApiName=instance.reference.getAttribute('data-augment-apiname');const augmentData=augmentTooltipDataGlobal[augmentApiName];if(augmentData){const tooltipContent=generateAugmentTooltipHTML(augmentData);instance.setContent(tooltipContent);}else{instance.setContent('Augment data not found.');}},});function generateAugmentTooltipHTML(data){const imageHTML=`
            <div class="augment-image">
                <img decoding="async" src="${data.icon_url}" alt="${data.name}">
            </div>
        `;const titleHTML=`
            <div class="augment-title">
                ${data.name}
            </div>
        `;const stagesHTML=generateStagesHTML(data.ItemTags||[]);const dividerHTML=`
            <div class="divider07"></div>
        `;const compositions=getCompositionsForAugment(data.apiName);const descriptionHTML=`
            <div class="augment-description">
                ${parseAugmentDescription(data.desc_parsed)}
            </div>
        `;let compositionsHTML='';if(compositions.length>0){compositionsHTML=`
                <div class="divider07"></div>
                <div class="condition-tooltip-comps">
                    ${generateCompositionsByTierHTML(compositions)}
                </div>
            `;}
return`
            <div class="augment-tooltip">
                ${imageHTML}
                ${titleHTML}
                ${stagesHTML}
                ${dividerHTML}
                ${descriptionHTML}
                ${compositionsHTML}
            </div>
        `;}
function generateStagesHTML(itemTags){const hasD22ae649=itemTags.some(tag=>tag.includes('d22ae649'));const hasD02ae323=itemTags.some(tag=>tag.includes('d02ae323'));const hasD12ae4b6=itemTags.some(tag=>tag.includes('d12ae4b6'));let hideStage21=false;let hideStage32=false;let hideStage42=false;if(hasD22ae649&&!hasD02ae323&&!hasD12ae4b6){hideStage42=true;}else if(hasD02ae323&&!hasD12ae4b6&&!hasD22ae649){hideStage21=true;}else if(hasD12ae4b6&&hasD22ae649){hideStage32=true;hideStage42=true;}else if(hasD02ae323&&hasD22ae649){hideStage21=true;hideStage42=true;}else if(hasD02ae323&&hasD12ae4b6){hideStage21=true;hideStage32=true;}
return`
            <div class="augment-stage-container">
                <span class="augment-stage-label">Offered on:</span>
                <div class="augment-stage${hideStage21 ? ' hide' : ''}">2-1</div>
                <div class="augment-stage${hideStage32 ? ' hide' : ''}">3-2</div>
                <div class="augment-stage${hideStage42 ? ' hide' : ''}">4-2</div>
            </div>
        `;}
function parseAugmentDescription(desc){if(!desc)return'';const iconsWithSvg=['scaleAP','scaleMana','scaleAD','scaleAS','scaleDA','scaleDR','scaleArmor','scaleMR','scaleSV','scaleHealth','scaleCrit','goldCoins'];desc=desc.replace(/%i:([^%]+)%/g,(match,iconName)=>{const iconBaseName=iconName;const iconUrlSvg=`/wp-content/uploads/tooltip/icons/${iconBaseName}.svg`;const iconUrlPng=`/wp-content/uploads/tooltip/icons/${iconBaseName}.png`;const hasSvg=iconsWithSvg.includes(iconBaseName);const iconUrl=hasSvg?iconUrlSvg:iconUrlPng;return`<img src="${iconUrl}" alt="${iconName} Icon" class="icon-inline">`;});desc=desc.replace(/<([^>]+)>(.*?)<\/\1>/g,(match,tagName,innerText)=>{if(tagName==='br'||tagName==='li'){return`<${tagName}>${innerText}</${tagName}>`;}else{return`<span class="${tagName}">${innerText}</span>`;}});return desc;}
function getCompositionsForAugment(augmentApiName){if(!window.compositionDataGlobal||!augmentApiName){return[];}
const compositions=[];const addedCompositions=new Set();Object.values(window.compositionDataGlobal).forEach(comp=>{let foundInRequired=false;let foundInStrong=false;let strongConditionTierModifier=0;if(comp.required_condition&&comp.required_condition.type==='Augments'&&comp.required_condition.data&&comp.required_condition.data.apiName===augmentApiName){foundInRequired=true;}
if(comp.strong_conditions&&Array.isArray(comp.strong_conditions)){comp.strong_conditions.forEach(condition=>{if(condition.type==='Augments'&&condition.data&&condition.data.apiName===augmentApiName){foundInStrong=true;strongConditionTierModifier=condition.tierModifier||0;}});}
const foundInCompositionAugments=false;if((foundInRequired||foundInStrong||foundInCompositionAugments)&&!addedCompositions.has(comp.ID)){let tierModifier=0;if(foundInStrong){tierModifier=strongConditionTierModifier;}else{tierModifier=0;}
compositions.push({id:comp.ID,name:comp.name,representative_champion:comp.representative_champion,composition_tier:comp.composition_tier,tier_modifier:tierModifier});addedCompositions.add(comp.ID);}});return compositions;}
function generateCompositionsByTierHTML(compositions){const tierOrder={'OP':7,'S+':6,'S':5,'A':4,'B':3,'C':2,'D':1};compositions.sort((a,b)=>{const modifiedTierA=calculateModifiedTier(a.composition_tier,a.tier_modifier);const modifiedTierB=calculateModifiedTier(b.composition_tier,b.tier_modifier);const tierValueA=tierOrder[modifiedTierA]||3;const tierValueB=tierOrder[modifiedTierB]||3;if(tierValueA!==tierValueB){return tierValueB-tierValueA;}
return a.name.localeCompare(b.name);});const limitedCompositions=compositions.slice(0,10);return limitedCompositions.map(comp=>generateCompositionItemHTML(comp)).join('');}
function calculateModifiedTier(baseTier,tierModifier){const tierValues={'D':1,'C':2,'B':3,'A':4,'S':5,'S+':6,'OP':7};const tierNames={1:'D',2:'C',3:'B',4:'A',5:'S',6:'S+',7:'OP'};const baseValue=tierValues[baseTier]||3;const modifiedValue=Math.min(7,Math.max(1,baseValue+tierModifier));return tierNames[modifiedValue];}
function generateCompositionItemHTML(comp){const compUrl=`${window.location.origin}/?p=${comp.id}`;let championImg='';let championApiname='';if(comp.representative_champion&&window.championDataGlobal&&window.championDataGlobal[comp.representative_champion]){const champion=window.championDataGlobal[comp.representative_champion];championImg=champion.tileIcon_url||champion.icon_url;championApiname=comp.representative_champion;}
const modifiedTier=calculateModifiedTier(comp.composition_tier,comp.tier_modifier);const tierClass='flow-image-sTier';let html=`<a rel="noopener noreferrer" class="tooltip-comp-link no-lightbox" href="${compUrl}">`;if(championImg){html+=`<img data-champion-apiname="${championApiname}" alt="${comp.name}" src="${championImg}" class="champion-icon ${tierClass}" decoding="async">`;}
html+=`<span class="tier-label"><span class="tier-dropdown-label" data-value="${modifiedTier}">${modifiedTier}</span></span>`;html+=`<div class="comp-name">${comp.name}</div>`;html+='</a>';return html;}});