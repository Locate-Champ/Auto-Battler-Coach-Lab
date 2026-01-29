jQuery(document).ready(function($){if(typeof championDataGlobal==='undefined'){console.error('Champion data not found for unlock tooltips.');return;}
tippy.delegate('body',{target:'.unlock-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'unlock-tooltip-theme',touch:false,onShow(instance){const championApiName=instance.reference.getAttribute('data-champion-apiname');const championData=championDataGlobal[championApiName];if(championData&&championData.unlock_conditions){const tooltipContent=generateUnlockTooltipHTML(championData.unlock_conditions,championData);instance.setContent(tooltipContent);}else{instance.setContent('Unlock data not found.');}},});tippy.delegate('body',{target:'.builder-unlock-icon',content:'Loading...',allowHTML:true,interactive:false,delay:[800,0],maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'unlock-tooltip-theme',onShow(instance){if(!instance.reference.isConnected){return false;}
const championApiName=instance.reference.getAttribute('data-champion-apiname');const championData=championDataGlobal[championApiName];if(championData&&championData.unlock_conditions){const tooltipContent=generateUnlockTooltipHTML(championData.unlock_conditions,championData);instance.setContent(tooltipContent);}else{instance.setContent('Unlock data not found.');}},});function generateUnlockTooltipHTML(unlockData,championData){const requiredLevel=unlockData.required_level;const descriptions=unlockData.description_parsed;if(!descriptions||descriptions.length===0){return'<div class="unlock-tooltip">No unlock conditions available.</div>';}
const championName=championData.name||'Unknown Champion';const championApiName=championData.apiName||'';const championIcon=championData.tileIcon_url||'/wp-content/uploads/tooltip/icons/questionMark.svg';const championCost=parseInt(championData.cost,10);let costClass='cost6';if(championCost>=1&&championCost<=6){costClass=`cost${championCost}`;}
const levelText=requiredLevel?`Level ${requiredLevel}`:'No Level Requirement';let conditionsHTML='';if(descriptions.length===1){conditionsHTML=`
    <div class="champion-unlock-condition">
      ${descriptions[0]}
    </div>`;}else{conditionsHTML=`
    <div class="champion-unlock-multiple-conditions">
      Must complete ALL conditions
    </div>
    <ul class="champion-unlock-condition-list">`;descriptions.forEach(desc=>{conditionsHTML+=`
      <li>${desc}</li>`;});conditionsHTML+=`
    </ul>`;}
return`
            <div class="unlock-tooltip">
                <div class="champion-unlock-container">
    <img src="${championIcon}" alt="${championName}" class="champion-icon unlock-tooltip-champion-icon ${costClass}" data-champion-apiname="${championApiName}">
    <div class="champion-unlock-title">${championName}</div>
    <div class="divider06"></div>
    <div class="champion-unlock-header">
      <img class="champion-unlock-icon" src="/wp-content/uploads/tooltip/icons/unlockIcon.svg">
      <div class="champion-unlock-level">${levelText}</div>
    </div>${conditionsHTML}
  </div>
            </div>
        `;}});