jQuery(document).ready(function($){if(typeof openerDataGlobal==='undefined'){console.error('Opener tooltip data not found.');return;}
tippy.delegate('body',{target:'.opener-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'opener-tooltip-theme',onShow(instance){const openerId=instance.reference.getAttribute('data-opener-id');const openerData=findOpenerData(openerId);if(openerData){const tooltipContent=generateOpenerTooltipHTML(openerData);instance.setContent(tooltipContent);}else{instance.setContent('Opener data not found.');}},});function findOpenerData(openerId){if(!openerId)return null;for(const setKey in openerDataGlobal){if(openerDataGlobal[setKey]){for(const openerKey in openerDataGlobal[setKey]){const openerData=openerDataGlobal[setKey][openerKey];if(openerData&&openerData.ID==openerId){return openerData;}}}}
return null;}
function generateOpenerTooltipHTML(data){let championListsHTML='';if(data.opener_variations&&data.opener_variations.length>0){const maxVariations=Math.min(3,data.opener_variations.length);for(let i=0;i<maxVariations;i++){const variation=data.opener_variations[i];if(variation&&variation.length>0){championListsHTML+=generateChampionListHTML(variation);}}}
const variationCount=data.opener_variations?data.opener_variations.length:0;const titleSuffix=variationCount>1?'Openers':'Opener';const titleHTML=`
            <div class="opener-title">
                ${data.opener_name} ${titleSuffix}
            </div>
        `;const compositions=getCompositionsForOpener(data.ID);let compositionsHTML='';if(compositions.length>0){compositionsHTML=`
                <div class="divider07"></div>
                <div class="condition-tooltip-comps">
                    ${generateCompositionsByTierHTML(compositions)}
                </div>
            `;}
return`
            <div class="opener-tooltip">
                ${championListsHTML}
                ${titleHTML}
                ${compositionsHTML}
            </div>
        `;}
function generateChampionListHTML(championApiNames){if(!championApiNames||championApiNames.length===0){return'';}
const sortedChampions=championApiNames.slice().sort((a,b)=>{const costA=getChampionCost(a);const costB=getChampionCost(b);return costA-costB;});let championListHTML='<div class="opener-champion-list">';sortedChampions.forEach(championApiName=>{const championData=getChampionData(championApiName);if(championData){const cost=championData.cost;const championImageUrl=championData.tileIcon_url||championData.icon_url;const championName=championData.name||championApiName;championListHTML+=`<img decoding="async" src="${championImageUrl}" alt="${championName}" class="champion-icon opener-champion-list-icon opener-champion-list-icon--cost${cost}" data-champion-apiname="${championApiName}">`;}else{console.warn(`Champion data not found for: ${championApiName}`);championListHTML+=`<img decoding="async" src="" alt="${championApiName}" class="champion-icon opener-champion-list-icon opener-champion-list-icon--cost6" data-champion-apiname="${championApiName}">`;}});championListHTML+='</div>';return championListHTML;}
function getChampionData(apiName){if(typeof championDataGlobal!=='undefined'&&championDataGlobal[apiName]){return championDataGlobal[apiName];}
return null;}
function getChampionCost(apiName){if(typeof championDataGlobal!=='undefined'&&championDataGlobal[apiName]&&typeof championDataGlobal[apiName].cost!=='undefined'){return championDataGlobal[apiName].cost;}
return 6;}
function getCompositionsForOpener(openerId){if(!window.compositionDataGlobal||!openerId){return[];}
const compositions=[];const addedCompositions=new Set();Object.values(window.compositionDataGlobal).forEach(comp=>{let foundInRequired=false;let foundInStrong=false;let strongConditionTierModifier=0;if(comp.required_condition&&comp.required_condition.type==='Openers'&&comp.required_condition.data&&comp.required_condition.data.ID===parseInt(openerId)){foundInRequired=true;}
if(comp.strong_conditions&&Array.isArray(comp.strong_conditions)){comp.strong_conditions.forEach(condition=>{if(condition.type==='Openers'&&condition.data&&condition.data.ID===parseInt(openerId)){foundInStrong=true;strongConditionTierModifier=condition.tierModifier||0;}});}
const foundInAssociated=comp.associated_openers&&comp.associated_openers.includes(parseInt(openerId));if((foundInRequired||foundInStrong||foundInAssociated)&&!addedCompositions.has(comp.ID)){let tierModifier=0;if(foundInStrong){tierModifier=strongConditionTierModifier;}else{tierModifier=0;}
compositions.push({id:comp.ID,name:comp.name,representative_champion:comp.representative_champion,composition_tier:comp.composition_tier,tier_modifier:tierModifier});addedCompositions.add(comp.ID);}});return compositions;}
function generateCompositionsByTierHTML(compositions){const tierOrder={'OP':7,'S+':6,'S':5,'A':4,'B':3,'C':2,'D':1};compositions.sort((a,b)=>{const modifiedTierA=calculateModifiedTier(a.composition_tier,a.tier_modifier);const modifiedTierB=calculateModifiedTier(b.composition_tier,b.tier_modifier);const tierValueA=tierOrder[modifiedTierA]||3;const tierValueB=tierOrder[modifiedTierB]||3;if(tierValueA!==tierValueB){return tierValueB-tierValueA;}
return a.name.localeCompare(b.name);});const limitedCompositions=compositions.slice(0,10);return limitedCompositions.map(comp=>generateCompositionItemHTML(comp)).join('');}
function calculateModifiedTier(baseTier,tierModifier){const tierValues={'D':1,'C':2,'B':3,'A':4,'S':5,'S+':6,'OP':7};const tierNames={1:'D',2:'C',3:'B',4:'A',5:'S',6:'S+',7:'OP'};const baseValue=tierValues[baseTier]||3;const modifiedValue=Math.min(7,Math.max(1,baseValue+tierModifier));return tierNames[modifiedValue];}
function generateCompositionItemHTML(comp){const compUrl=`${window.location.origin}/?p=${comp.id}`;let championImg='';let championApiname='';if(comp.representative_champion&&window.championDataGlobal&&window.championDataGlobal[comp.representative_champion]){const champion=window.championDataGlobal[comp.representative_champion];championImg=champion.tileIcon_url||champion.icon_url;championApiname=comp.representative_champion;}
const modifiedTier=calculateModifiedTier(comp.composition_tier,comp.tier_modifier);const tierClass='flow-image-sTier';let html=`<a rel="noopener noreferrer" class="tooltip-comp-link no-lightbox" href="${compUrl}">`;if(championImg){html+=`<img data-champion-apiname="${championApiname}" alt="${comp.name}" src="${championImg}" class="champion-icon ${tierClass}" decoding="async">`;}
html+=`<span class="tier-label"><span class="tier-dropdown-label" data-value="${modifiedTier}">${modifiedTier}</span></span>`;html+=`<div class="comp-name">${comp.name}</div>`;html+='</a>';return html;}});