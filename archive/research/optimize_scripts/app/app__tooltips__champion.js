jQuery(document).ready(function($){if(typeof championDataGlobal==='undefined'){console.error('Champion data not found.');return;}
tippy.delegate('body',{target:'.champion-icon',content:'Loading...',allowHTML:true,interactive:false,maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'champion-tooltip-theme',onShow(instance){const championApiName=instance.reference.getAttribute('data-champion-apiname');const championData=championDataGlobal[championApiName];if(championData){const tooltipContent=generateChampionTooltipHTML({champion:championData});instance.setContent(tooltipContent);}else{instance.setContent('Champion data not found.');}},});tippy.delegate('body',{target:'.builder-champion-icon',content:'Loading...',allowHTML:true,interactive:false,delay:[800,0],maxWidth:'none',placement:'auto',appendTo:()=>document.body,theme:'champion-tooltip-theme',onShow(instance){if(!instance.reference.isConnected){return false;}
const championApiName=instance.reference.getAttribute('data-champion-apiname');const championData=championDataGlobal[championApiName];if(championData){const tooltipContent=generateChampionTooltipHTML({champion:championData});instance.setContent(tooltipContent);}else{instance.setContent('Champion data not found.');}},});function parseChampionDescription(desc){if(!desc)return'';const iconsWithSvg=['scaleAP','scaleMana','scaleAD','scaleAS','scaleDA','scaleDR','scaleArmor','scaleMR','scaleSV','scaleHealth','scaleCrit','scaleCritMult','scaleRange','goldCoins','hp','mana'];desc=desc.replace(/%i:([^%]+)%/g,(match,iconName)=>{const iconBaseName=iconName;const iconUrlSvg=`/wp-content/uploads/tooltip/icons/${iconBaseName}.svg`;const iconUrlPng=`/wp-content/uploads/tooltip/icons/${iconBaseName}.png`;const hasSvg=iconsWithSvg.includes(iconBaseName);const iconUrl=hasSvg?iconUrlSvg:iconUrlPng;return`<img src="${iconUrl}" alt="${iconName} Icon" class="icon-inline">`;});desc=desc.replace(/<row>(.*?)<\/row>/g,(match,innerText)=>{return`${innerText}`;});desc=desc.replace(/<\/?expandRow>/g,'');desc=desc.replace(/<([^>]+)>(.*?)<\/\1>/g,(match,tagName,innerText)=>{if(tagName==='br'||tagName==='li'){return`<${tagName}>${innerText}</${tagName}>`;}else{return`<span class="${tagName}">${innerText}</span>`;}});return desc;}
function generateUnlockConditionsHTML(champion){if(!champion.unlock_conditions||champion.unlock_conditions===null){return'';}
const unlockData=champion.unlock_conditions;const requiredLevel=unlockData.required_level;const descriptions=unlockData.description_parsed;if(!descriptions||descriptions.length===0){return'';}
function processDescription(desc){let processed=desc.replace(/\\"/g,'"').replace(/\\'/g,"'");return parseChampionDescription(processed);}
const levelText=requiredLevel?`Level ${requiredLevel}`:'No Level Requirement';let unlockHtml=`
            <div class="champion-unlock-container">
                <div class="champion-unlock-header">
                    <img class="champion-unlock-icon" src="/wp-content/uploads/tooltip/icons/unlockIcon.svg">
                    <div class="champion-unlock-level">${levelText}</div>
                </div>
        `;if(descriptions.length===1){unlockHtml+=`
                <div class="champion-unlock-condition">
                    ${processDescription(descriptions[0])}
                </div>
            `;}else{unlockHtml+=`
                <div class="champion-unlock-multiple-conditions">
                    Must complete ALL conditions
                </div>

                <ul class="champion-unlock-condition-list">
            `;descriptions.forEach(desc=>{unlockHtml+=`
                    <li>
                        ${processDescription(desc)}
                    </li>
                `;});unlockHtml+=`
                </ul>
            `;}
unlockHtml+=`
            </div>

            <!-- Divider after unlock conditions -->
            <div class="divider06"></div>
        `;return unlockHtml;}
function generateChampionTooltipHTML(data){const champion=data.champion;const cost=champion.cost;const costClass=cost>=1&&cost<=5?`champion-tooltip--cost${cost}`:'champion-tooltip--cost6';const rarityBannerUrl=cost>=1&&cost<=5?`/wp-content/uploads/tooltip/banners/raritybanner0${cost}.png`:`/wp-content/uploads/tooltip/banners/raritybanner06.png`;const championImageUrl=champion.icon_url;const abilityIconUrl=champion.ability_icon_url;const traits=champion.traits;const traitsHtml=traits.map(trait=>`
            <div class="champion-trait-item">
                <img src="${trait.icon_url}" alt="${trait.name} Icon">
                <div class="champion-trait-name">${trait.name}</div>
            </div>
        `).join('');const initialMana=champion.initialMana;const mana=champion.mana;const manaBarWidth=mana>0?((initialMana/mana)*100).toFixed(1):0;const abilityDescription=parseChampionDescription(champion.ability_desc_parsed);const unlockConditionsHtml=generateUnlockConditionsHTML(champion);const hasUnlockConditions=champion.unlock_conditions&&champion.unlock_conditions!==null;const unlockCornerIcon=hasUnlockConditions?'<img class="comp-info-headliner-icon champion-unlock-icon champion-unlock-icon--corner" src="/wp-content/uploads/tooltip/icons/unlockIcon.svg">':'';return`
        <div class="champion-tooltip ${costClass}">
            <div class="champion-tooltip-border">
                ${unlockCornerIcon}
                <!-- Champion Image -->
                <div class="champion-image" style="background-image: url('${championImageUrl}')">
                    <!-- Traits Overlay -->
                    <div class="champion-traits-overlay">
                        ${traitsHtml}
                    </div>
                </div>

                <!-- Rarity Banner -->
                <div class="champion-rarity-banner" style="background-image: url('${rarityBannerUrl}')">
                    <span>${champion.name}</span>
                    <span><img src="/wp-content/uploads/tooltip/icons/goldCoins.svg" alt="Cost Icon"> ${cost}</span>
                </div>

                <!-- Green HP Bar -->
                <div class="champion-hp-bar">
                    <span class="champion-hp-amount">${champion.hp} HP</span>
                </div>

                <!-- Blue Mana Bar -->
                <div class="champion-mana-bar-container">
                    <div class="champion-mana-bar" style="width: ${manaBarWidth}%"></div>
                    <span class="champion-mana-bar-text">${initialMana} / ${mana}</span>
                </div>

                <!-- No-gap divider between Mana and Ability -->
                <div class="divider06"></div>

                ${unlockConditionsHtml}

                <!-- Ability Section -->
                <div class="champion-ability-container">
                    <div class="champion-ability-header">
                        <div class="champion-ability-icon">
                            <img src="${abilityIconUrl}" alt="Ability Icon">
                            <strong>${champion.ability_name}</strong>
                        </div>
                        <div class="champion-range">
                            <img src="/wp-content/uploads/tooltip/icons/scaleRange.svg" alt="Range Icon">
                            <span>${champion.range} Hex</span>
                        </div>
                    </div>
                    <div class="champion-ability-description">
                        ${abilityDescription}
                    </div>
                </div>
            </div>
        </div>
        `;}});