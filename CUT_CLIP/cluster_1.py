import os
import numpy as np
from tqdm import tqdm
from PIL import Image
import torch

from torchvision import transforms

from data import create_dataset
from options.test_options import TestOptions

import clip
from modelprompt import PromptLearner

device = 'cuda'

clip_model, preprocess = clip.load('ViT-B/32', device="cpu", jit=False) 
""" freeze the network parameters """
for clip_param in clip_model.parameters():
    clip_param.requires_grad = False
clip_model = clip_model.to(device)

def set_input(input):
    real_A = input['A'].to(device)
    image_path = input['A_paths']
    label = input["label"]
    return real_A, image_path, label

""" start, 여기만 바꿔주세요!, promptlearner에서 추출하고 싶으면 class_prompt선언이 끝난 후 코드(약 97번째 이후.)를 봐주세요! """

""" dataset"""
use_promptLearner = False #(97번째 줄 이후 모두 주석 풀면 자동으로 True로 바뀜.)

# dataset = "celeb" # animal, food, celeb : 데이터셋 이름.
# n = 4 # n= 4, 7, 10 # num_domains
# dir_A = "/root/project/datasets/food"#"/root/project/datasets/CelebAMask-HQ/celeba" # 데이터셋 경로.
# save_root = "./clip_celeb_4_PL74000" # 저장할 디렉토리 경로.

# dataset = "animal" # animal, food, celeb : 데이터셋 이름.
# n = 10 # n= 4, 7, 10 # num_domains
# dir_A = "/root/project/datasets/af_10" #"/root/project/datasets/CelebAMask-HQ/celeba" # 데이터셋 경로.
# save_root = "./clip_af_10_PL44000"      # 저장할 디렉토리 경로.

dataset = "celeb" # animal, food, celeb : 데이터셋 이름.
n = 7 # n= 4, 7, 10 # num_domains
dir_A = "/root/project/datasets/CelebAMask-HQ/celeba"#"/root/project/datasets/CelebAMask-HQ/celeba" # 데이터셋 경로.
save_root = "./clip_celeb_7_PL091000" # 저장할 디렉토리 경로.

# celeba, ffhq, dir_A = "/root/project/datasets/CelebAMask-HQ/celeba"
# animalface,  dir_A =  "/root/project/datasets/af_10"
# food10,      dir_A =  "/root/project/datasets/food"

# celebahq 데이터셋 사용할 경우에만 필요.
ffhq_anno_path = "/root/project/datasets/CelebAMask-HQ/CelebAMask-HQ-attribute-anno.txt"
""" end """


if "animal" in dataset:
    template = 'a photo of the {}.'
    
    if n == 4:
        # af4
        class_prompt = ['beagle', 'golden retriever','tabby cat', 'bengal tiger']
    elif n==7:
        # af7
        class_prompt = ['beagle', 'dandie dinmont terrier', 'golden retriever', 'white fox', 'tabby cat', 'snow leopard', 'bengal tiger']
    elif n == 10:
        # af10
        class_prompt = ['beagle', 'dandie dinmont terrier', 'golden retriever', 'malinois',\
                        'appenzeller sennenhund', 'white fox', 'tabby cat', 'snow leopard', 'lion', 'bengal tiger']

    base_prompt = ["a photo of the animal face."]


elif "food" in dataset:
    template = 'a photo of the {}.'
    if n == 4:
        # food 4
        class_prompt = ['baby back ribs', 'beignets', 'dumplings','edamame']
    elif n == 7:
        # food 7
        class_prompt = ['baby back ribs','beef carpaccio','beignets','clam chowder','dumplings','edamame', 'strawberry shortcake' ]
    elif n == 10:
        # food 10
        class_prompt =  [ "baby back ribs", "beef carpaccio", "French beignets", "Korean bibimbap", "caesar salad",\
                            "clam chowder", "Chinese dumplings", "edamame", "spaghetti bolognese", "strawberry shortcake"]
    base_prompt = ["a photo of the food."]

elif "celeb" or "ffhq" in dataset:
    template = 'a face with {}.'

    if n == 4:
        # celeb4
        class_prompt = ['blond hair', 'black hair' , 'smiling', 'eyeglasses',] 
        print()
    elif n == 7:
        # celeb7
        class_prompt =  ['blond hair', 'wavy hair', 'black hair' , 'smiling', 'eyeglasses', 'goatee', 'bangs',]
        print()
    elif n == 10:
        # celeb10
        class_prompt = ['blond hair', 'bald', 'wavy hair', 'black hair' ,\
                        'smiling', 'straight hair', 'eyeglasses', 'goatee', 'bangs', 'arched eyebrows'] 
        #['bangs', 'blond hair', 'bald', 'wavy hair', 'black hair' , 'gray hair', 'young', 'pale skin','heavy makeup','no beard','mustache']
    
    base_prompt = ["a face."]


""" model """
""" 모두 주석 처리하거나, 풀거나. :prompyleaner에서 text를 뽑기위해서, model load하는 경우. """
use_promptLearner = True
#checkpoint_path = '/root/data/lunit_weight_step2/food-10_step2/074000_nets.ckpt'
#checkpoint_path = '/root/data/lunit_weight_step2/af-10_step2/044000_nets.ckpt'
checkpoint_path = '/root/data/lunit_weight_step2/celeb-7_step2/091000_nets.ckpt'
checkpoint = torch.load(checkpoint_path, map_location='cuda')
promptLearner = torch.nn.DataParallel(PromptLearner(device="cuda", K=len(class_prompt), init_prompt=template, classes=class_prompt, clip_model=clip_model, rand_token_len=4))
promptLearner.module.load_state_dict(checkpoint["promptLearner"])
""" end """

prompt = [template.format(x) for x in class_prompt]

""" option 설정 """
opt = TestOptions().parse()
opt.__setattr__("dataset", dataset)
opt.__setattr__("dir_A", dir_A)
opt.__setattr__("anno_path", ffhq_anno_path)

dataset = create_dataset(opt)
print(opt)

with torch.no_grad():
    """ 모든 topk에 대해서 조사."""
    topk_all_sim_list  = np.array([ 0 for i in range(len(class_prompt)) ])
    topk_all_imgpath_list = np.array([ 0 for i in range(len(class_prompt)) ])

    """ list for save """
    topk_perclass_sim_list  = [ [ [] for i in range(len(class_prompt))  ] for i in range(len(class_prompt)) ]
    topk_perclass_rel_sim_list  = [ [ [] for i in range(len(class_prompt))  ] for i in range(len(class_prompt)) ]

    topk_perclass_vector_list  = [ [ [] for i in range(len(class_prompt))  ] for i in range(len(class_prompt)) ]
    topk_perclass_rel_vector_list  = [ [ [] for i in range(len(class_prompt))  ] for i in range(len(class_prompt)) ]

    topk_perclass_imgpath_list  = [ [ [] for i in range(len(class_prompt))  ] for i in range(len(class_prompt)) ]

    """ pre-extract text feature """
    """ 이미지들만 바뀌기 때문에 매 itreation 마다 text feature를 추출할 필요가 없다. """
    if use_promptLearner:
        """ prompt learner 이용하는 경우"""
        text_feature = promptLearner(clip_model)
        text_feature = text_feature / text_feature.norm(dim=-1, keepdim=True)
        """ end """
    else:
        tokens = clip.tokenize(prompt).to(device)
        text_feature = clip_model.encode_text(tokens).detach()
        text_feature = text_feature / text_feature.norm(dim=-1, keepdim=True)
    
    base_tokens = clip.tokenize(base_prompt).to(device)
    base_text_feature = clip_model.encode_text(base_tokens).detach()
    base_text_feature = base_text_feature / base_text_feature.norm(dim=-1, keepdim=True)

    for idx, data in tqdm(enumerate(dataset)):
        real, image_path, label = set_input(data)

        image_features = clip_model.encode_image(real) # preprocess(image.open("CLIP.png")).unsqueeze(0).to(device)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        logit_scale = clip_model.logit_scale.exp()
        logits_per_image  = logit_scale * image_features @ text_feature.t() # (1, 7)

        """ base template과 비교 """
        logits_per_image_base  = logit_scale * image_features @ base_text_feature.t() # (1, 7)

        probs = logits_per_image.softmax(dim=-1).cpu().numpy()


        """
        logits_per_image.shape = (1, num_prompts)
        label.shape = (1, 1, num_label)
        """
        topk_val, topk_idx  = torch.topk(logits_per_image, k=len(prompt))
        topk_val, topk_idx  = topk_val[0], topk_idx[0]
        for k in range(len(prompt)):
            idx = int(topk_idx[k].item())
            val = topk_val[k].item()

            """ topk번째, similarity value 저장. """
            topk_perclass_sim_list[idx][k].append(val) # 도메인당, topk구별해서 또 저장.
            topk_perclass_rel_sim_list[idx][k].append(val-logits_per_image_base.item()) # 도메인당, topk구별해서 또 저장.

            """ similarity vector 저장. """
            topk_perclass_vector_list[idx][k].append(logits_per_image[0].cpu().numpy())
            topk_perclass_rel_vector_list[idx][k].append( (logits_per_image-logits_per_image_base)[0].cpu().numpy())
  
            """ img path 저장 """
            topk_perclass_imgpath_list[idx][k].append(image_path)

os.makedirs(save_root, exist_ok=True)
np.save( os.path.join(save_root, "topk_sim_perclass")         , np.array(topk_perclass_sim_list))
np.save( os.path.join(save_root, "topk_rel_sim_perclass")     , np.array(topk_perclass_rel_sim_list))

np.save( os.path.join(save_root, "topk_vector_perclass")      , np.array(topk_perclass_vector_list))
np.save( os.path.join(save_root, "topk_rel_vector_perclass")  , np.array(topk_perclass_rel_vector_list))

np.save( os.path.join(save_root, "topk_sim_perclass_imgpath") , np.array(topk_perclass_imgpath_list))
